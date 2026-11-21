from __future__ import annotations

import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_config
from app.core.errores import ErrorNegocio, NoEncontrado
from app.core.reloj import now
from app.dominios.juego.repositorio import JuegoRepositorio
from app.dominios.juego.servicio import JuegoServicio
from app.esquemas.juego import EnviarRespuestaInput
from app.esquemas.sync import (
    EstadoJugadorSync,
    IntentoSyncResumen,
    ResultadoSync,
    SyncRespuestasInput,
    SyncRespuestasRespuesta,
)
from app.modelos.enums import EstadoCuenta, EstadoIntento


class SyncServicio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion
        self._repo = JuegoRepositorio(sesion)

    def _calcular_vidas_efectivas(self, usuario: Any) -> int:
        cfg = get_config()
        ahora = now()
        delta_s = (ahora - usuario.vidas_base_en).total_seconds()
        regeneradas = int(delta_s // cfg.VIDA_REGEN_SEGUNDOS)
        return min(cfg.VIDAS_MAX, usuario.vidas + regeneradas)

    async def sincronizar(
        self, usuario_id: uuid.UUID, datos: SyncRespuestasInput
    ) -> SyncRespuestasRespuesta:
        usuario = await self._repo.buscar_usuario_con_lock(usuario_id)
        if usuario is None or usuario.estado_cuenta != EstadoCuenta.activo:
            raise NoEncontrado()

        resultados: list[ResultadoSync] = []
        intentos_map: dict[str, IntentoSyncResumen] = {}
        juego_svc = JuegoServicio(self._s)

        for elem in datos.respuestas:
            existente = await self._repo.buscar_respuesta_por_id(elem.id)
            if existente is not None:
                resultados.append(ResultadoSync(id=elem.id, estado="duplicada"))
                continue

            intento = await self._repo.buscar_intento_por_id(elem.intento_id)
            if intento is None or intento.usuario_id != usuario_id:
                resultados.append(
                    ResultadoSync(id=elem.id, estado="rechazada", motivo="NO_ENCONTRADO")
                )
                continue

            if intento.estado != EstadoIntento.en_curso:
                resultados.append(
                    ResultadoSync(id=elem.id, estado="rechazada", motivo="INTENTO_CERRADO")
                )
                continue

            try:
                resp_input = EnviarRespuestaInput(
                    id=elem.id,
                    tarjeta_id=elem.tarjeta_id,
                    veredicto=elem.veredicto,
                    segundos=elem.segundos,
                    por_que_opcion_id=elem.por_que_opcion_id,
                    lineas_subrayadas=elem.lineas_subrayadas,
                    justificacion_opcion_id=elem.justificacion_opcion_id,
                    respondido_en=elem.respondido_en,
                )
                res_envio = await juego_svc.enviar_respuesta(
                    usuario_id, elem.intento_id, resp_input
                )
                resultados.append(
                    ResultadoSync(
                        id=elem.id,
                        estado="aplicada",
                        resultado=res_envio.resultado,
                    )
                )
                intentos_map[str(elem.intento_id)] = IntentoSyncResumen(
                    id=elem.intento_id,
                    estado=res_envio.estado_intento,
                    indicadores=res_envio.indicadores,
                    cierre=res_envio.cierre,
                )
            except ErrorNegocio as exc:
                resultados.append(
                    ResultadoSync(
                        id=elem.id,
                        estado="rechazada",
                        motivo=exc.codigo,
                    )
                )
            except Exception:
                resultados.append(
                    ResultadoSync(
                        id=elem.id,
                        estado="rechazada",
                        motivo="ERROR_INTERNO",
                    )
                )

        usuario_actualizado = await self._repo.buscar_usuario_con_lock(usuario_id)
        u = usuario_actualizado if usuario_actualizado is not None else usuario
        vidas_efectivas = self._calcular_vidas_efectivas(u)

        jugador = EstadoJugadorSync(
            vidas=vidas_efectivas,
            monedas=u.monedas,
            xp=u.xp,
            nivel=u.nivel,
            racha_actual=u.racha_actual,
            amparo_activo=u.amparo_activo,
        )

        return SyncRespuestasRespuesta(
            resultados=resultados,
            jugador=jugador,
            intentos=list(intentos_map.values()),
        )
