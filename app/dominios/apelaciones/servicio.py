from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_config
from app.core.errores import NoEncontrado, PeticionInvalida
from app.core.reloj import now
from app.dominios.apelaciones.repositorio import ApelacionesRepositorio
from app.esquemas.apelaciones import (
    ApelacionResumen,
    BuzonApelacionesRespuesta,
    DetalleApelacionRespuesta,
    EnviarJuicioInput,
    JuicioRespuesta,
)
from app.modelos.apelaciones import JuicioApelacion
from app.modelos.economia import MovimientoEconomia
from app.modelos.enums import EstadoApelacion, EstadoCuenta, ResultadoRespuesta, Veredicto


class ApelacionesServicio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion
        self._repo = ApelacionesRepositorio(sesion)

    def _calcular_vidas_efectivas(self, usuario: Any) -> int:
        cfg = get_config()
        ahora = now()
        delta_s = (ahora - usuario.vidas_base_en).total_seconds()
        regeneradas = int(delta_s // cfg.VIDA_REGEN_SEGUNDOS)
        return min(cfg.VIDAS_MAX, usuario.vidas + regeneradas)

    def _actualizar_racha(self, usuario: Any, ahora: Any) -> None:
        tz_str = usuario.zona_horaria or "America/Mexico_City"
        try:
            tz = ZoneInfo(tz_str)
        except Exception:
            tz = ZoneInfo("UTC")

        hoy = ahora.astimezone(tz).date()
        if usuario.ultimo_dia_racha == hoy:
            pass
        elif usuario.ultimo_dia_racha == hoy - timedelta(days=1):
            usuario.racha_actual = (usuario.racha_actual or 0) + 1
        else:
            usuario.racha_actual = 1

        usuario.ultimo_dia_racha = hoy
        usuario.racha_maxima = max(usuario.racha_maxima or 0, usuario.racha_actual)

    async def obtener_buzon(self, usuario_id: uuid.UUID) -> BuzonApelacionesRespuesta:
        ahora = now()
        apelaciones = await self._repo.listar_apelaciones_pendientes(usuario_id)

        vencidas: list[ApelacionResumen] = []
        proximas: list[ApelacionResumen] = []

        for ap in apelaciones:
            resumen = ApelacionResumen(
                id=ap.id,
                tarjeta_id=ap.tarjeta_id,
                tarjeta_version=ap.tarjeta_version,
                etapa=ap.etapa,
                proxima_revision=ap.proxima_revision,
                estado=ap.estado.value,
            )
            if ap.proxima_revision <= ahora:
                vencidas.append(resumen)
            else:
                proximas.append(resumen)

        return BuzonApelacionesRespuesta(vencidas=vencidas, proximas=proximas)

    async def obtener_detalle(
        self, usuario_id: uuid.UUID, apelacion_id: uuid.UUID
    ) -> DetalleApelacionRespuesta:
        ahora = now()
        apelacion = await self._repo.buscar_apelacion_por_id(apelacion_id)
        if apelacion is None or apelacion.usuario_id != usuario_id:
            raise NoEncontrado()

        if apelacion.proxima_revision > ahora:
            raise PeticionInvalida(detalle={"motivo": "Apelación no vencida todavía."})

        tarjeta = await self._repo.buscar_tarjeta_version(
            apelacion.tarjeta_id, apelacion.tarjeta_version
        )
        if tarjeta is None:
            raise NoEncontrado()

        ci = tarjeta.contenido_interactivo
        ev_claro = None
        if ci.get("evidencia"):
            ev = ci["evidencia"]
            ev_claro = {
                "formato": ev.get("formato"),
                "nombre_archivo": ev.get("nombre_archivo"),
                "contenido_texto": ev.get("contenido_texto"),
            }

        return DetalleApelacionRespuesta(
            id=apelacion.id,
            etapa=apelacion.etapa,
            tarjeta_id=tarjeta.id,
            tarjeta_version=tarjeta.version,
            texto=tarjeta.texto,
            categoria=tarjeta.categoria,
            personaje_nombre=tarjeta.personaje_nombre,
            personaje_rol=tarjeta.personaje_rol,
            iniciales=tarjeta.iniciales,
            evidencia=ev_claro,
        )

    async def resolver_juicio(
        self, usuario_id: uuid.UUID, apelacion_id: uuid.UUID, datos: EnviarJuicioInput
    ) -> JuicioRespuesta:
        cfg = get_config()
        ahora = now()

        usuario = await self._repo.buscar_usuario_con_lock(usuario_id)
        if usuario is None or usuario.estado_cuenta != EstadoCuenta.activo:
            raise NoEncontrado()

        apelacion = await self._repo.buscar_apelacion_con_lock(apelacion_id)
        if apelacion is None or apelacion.usuario_id != usuario_id:
            raise NoEncontrado()

        existente = await self._repo.buscar_juicio_por_id(datos.id)
        if existente is not None:
            vidas_act = self._calcular_vidas_efectivas(usuario)
            return JuicioRespuesta(
                resultado=existente.resultado.value,
                vida_recuperada=existente.vida_recuperada,
                etapa=apelacion.etapa,
                proxima_revision=apelacion.proxima_revision,
                estado=apelacion.estado.value,
                vidas=vidas_act,
            )

        if apelacion.proxima_revision > ahora:
            raise PeticionInvalida(detalle={"motivo": "Apelación no vencida todavía."})

        tarjeta = await self._repo.buscar_tarjeta_version(
            apelacion.tarjeta_id, apelacion.tarjeta_version
        )
        if tarjeta is None:
            raise NoEncontrado()

        ci = tarjeta.contenido_interactivo
        veredictos = ci.get("veredictos", {})
        if datos.veredicto not in veredictos:
            raise PeticionInvalida(detalle={"motivo": "Veredicto no válido."})

        resultado_str = veredictos[datos.veredicto]["resultado"]
        resultado_enum = ResultadoRespuesta(resultado_str)

        vida_recuperada = False
        if resultado_enum == ResultadoRespuesta.correcto:
            if apelacion.etapa == 1:
                apelacion.etapa = 2
                apelacion.proxima_revision = ahora + timedelta(days=cfg.APELACION_DIAS[1])
            elif apelacion.etapa == 2:
                apelacion.etapa = 3
                apelacion.proxima_revision = ahora + timedelta(days=cfg.APELACION_DIAS[2])
            else:
                apelacion.estado = EstadoApelacion.ganada
                vidas_base = self._calcular_vidas_efectivas(usuario)
                if vidas_base < cfg.VIDAS_MAX:
                    usuario.vidas = vidas_base + 1
                    vida_recuperada = True
                    await self._repo.crear_movimiento_economia(
                        MovimientoEconomia(
                            usuario_id=usuario.id,
                            recurso="vidas",
                            cantidad=1,
                            saldo_resultante=usuario.vidas,
                            motivo="apelacion_ganada",
                            detalle={"apelacion_id": str(apelacion.id)},
                            referencia_id=apelacion.id,
                        )
                    )
        else:
            apelacion.etapa = 1
            apelacion.proxima_revision = ahora + timedelta(days=cfg.APELACION_DIAS[0])

        juicio = JuicioApelacion(
            id=datos.id,
            apelacion_id=apelacion.id,
            veredicto=Veredicto(datos.veredicto),
            resultado=resultado_enum,
            vida_recuperada=vida_recuperada,
            resuelto_en=ahora,
        )
        await self._repo.crear_juicio(juicio)
        self._actualizar_racha(usuario, ahora)

        await self._s.commit()

        vidas_finales = self._calcular_vidas_efectivas(usuario)
        return JuicioRespuesta(
            resultado=resultado_str,
            vida_recuperada=vida_recuperada,
            etapa=apelacion.etapa,
            proxima_revision=apelacion.proxima_revision
            if apelacion.estado == EstadoApelacion.pendiente
            else None,
            estado=apelacion.estado.value,
            vidas=vidas_finales,
        )
