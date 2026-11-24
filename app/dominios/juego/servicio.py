from __future__ import annotations

import base64
import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_config
from app.core.errores import (
    ComodinYaUsado,
    IntentoCerrado,
    IntentoEnCurso,
    NoEncontrado,
    PausaAgotada,
    PausaNoPermitida,
    PeticionInvalida,
    SaldoInsuficiente,
    SinPermiso,
    SinVidas,
    SprintBloqueado,
    YaRespondida,
)
from app.core.reloj import now
from app.core.security import cifrar_resolucion, clave_intento_b64
from app.dominios.juego.repositorio import JuegoRepositorio
from app.esquemas.examen import (
    ContraargumentoInput,
    ContraargumentoRespuesta,
    DecisionExamen,
    IniciarExamenInput,
    IniciarExamenRespuesta,
    PausaRespuesta,
    ReanudarRespuesta,
)
from app.esquemas.juego import (
    AbandonarRespuesta,
    CierreIntentoRespuesta,
    EnviarRespuestaInput,
    EstadoIntentoRespuesta,
    IniciarSprintInput,
    PaqueteSprintRespuesta,
    PaqueteTarjeta,
    RecompensaRespuesta,
    RespuestaEnvioRespuesta,
    UsarComodinInput,
    UsarComodinRespuesta,
)
from app.esquemas.jsonb import Inventario, RetoDiario
from app.modelos.apelaciones import Apelacion
from app.modelos.contenido import Tarjeta
from app.modelos.economia import MovimientoEconomia
from app.modelos.logros import Certificado
from app.modelos.enums import (
    EstadoApelacion,
    EstadoCuenta,
    EstadoIntento,
    EstadoProgreso,
    ResultadoRespuesta,
    TipoIntento,
    TipoTarjeta,
    Veredicto,
)
from app.modelos.juego import Intento, ProgresoSprint, Respuesta


class JuegoServicio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion
        self._repo = JuegoRepositorio(sesion)

    def _calcular_vidas_efectivas(self, usuario: Any) -> tuple[int, Any]:
        cfg = get_config()
        ahora = now()
        delta_s = (ahora - usuario.vidas_base_en).total_seconds()
        regeneradas = int(delta_s // cfg.VIDA_REGEN_SEGUNDOS)
        vidas = min(cfg.VIDAS_MAX, usuario.vidas + regeneradas)

        proxima_en = None
        if vidas < cfg.VIDAS_MAX:
            residuo_s = delta_s % cfg.VIDA_REGEN_SEGUNDOS
            proxima_en = ahora + timedelta(seconds=cfg.VIDA_REGEN_SEGUNDOS - residuo_s)
        return vidas, proxima_en

    async def iniciar_sprint(
        self, usuario_id: uuid.UUID, sprint_id: int, datos: IniciarSprintInput
    ) -> PaqueteSprintRespuesta:
        cfg = get_config()
        usuario = await self._repo.buscar_usuario_con_lock(usuario_id)
        if usuario is None or usuario.estado_cuenta != EstadoCuenta.activo:
            raise NoEncontrado()

        existente_id = await self._repo.buscar_intento_por_id(datos.id)
        if existente_id is not None and existente_id.usuario_id == usuario_id:
            return await self._reconstruir_paquete(existente_id, usuario)

        vidas_efectivas, proxima_en = self._calcular_vidas_efectivas(usuario)
        if vidas_efectivas <= 0:
            raise SinVidas(
                detalle={"proxima_vida_en": proxima_en.isoformat() if proxima_en else None}
            )

        sprint = await self._repo.buscar_sprint(sprint_id)
        if sprint is None or sprint.es_examen:
            raise SprintBloqueado()

        progreso = await self._repo.buscar_progreso(usuario_id, sprint_id)
        if progreso is None or progreso.estado == EstadoProgreso.bloqueado:
            raise SprintBloqueado()

        en_curso = await self._repo.buscar_intento_en_curso(usuario_id)
        if en_curso is not None:
            raise IntentoEnCurso(detalle={"intento_id": str(en_curso.id)})

        activas = await self._repo.buscar_tarjetas_activas_sprint(sprint_id)
        normales = [t for t in activas if t.tipo == TipoTarjeta.normal]
        evidencias = [t for t in activas if t.tipo == TipoTarjeta.evidencia]
        justificaciones = [t for t in activas if t.tipo == TipoTarjeta.justificacion]

        if len(normales) < 6 or len(evidencias) < 3 or len(justificaciones) < 1:
            raise SprintBloqueado(detalle={"motivo": "contenido_insuficiente"})

        vistas = await self._repo.obtener_tarjetas_ultimos_intentos(usuario_id, sprint_id, limite=2)

        def _seleccionar(pool: list[Any], cantidad: int) -> list[Any]:
            no_vistas = [t for t in pool if t.id not in vistas]
            ya_vistas = [t for t in pool if t.id in vistas]
            random.shuffle(no_vistas)
            random.shuffle(ya_vistas)
            elegidas = no_vistas[:cantidad]
            if len(elegidas) < cantidad:
                elegidas.extend(ya_vistas[: (cantidad - len(elegidas))])
            return elegidas

        sel_normales = _seleccionar(normales, 6)
        sel_evidencias = _seleccionar(evidencias, 3)
        sel_justificaciones = _seleccionar(justificaciones, 1)

        diez_tarjetas = sel_normales + sel_evidencias + sel_justificaciones
        random.shuffle(diez_tarjetas)

        tarjetas_asignadas: list[dict[str, Any]] = []
        paquete_tarjetas: list[PaqueteTarjeta] = []

        for idx, t in enumerate(diez_tarjetas, start=1):
            tarjetas_asignadas.append(
                {
                    "orden": idx,
                    "tarjeta_id": str(t.id),
                    "version": t.version,
                    "comodines": [],
                }
            )

            ci = t.contenido_interactivo
            ev_claro = None
            if t.tipo == TipoTarjeta.evidencia and ci.get("evidencia"):
                ev = ci["evidencia"]
                ev_claro = {
                    "formato": ev.get("formato"),
                    "nombre_archivo": ev.get("nombre_archivo"),
                    "contenido_texto": ev.get("contenido_texto"),
                }

            mp_claro = {}
            if ci.get("micro_pregunta"):
                mp = ci["micro_pregunta"]
                mp_claro = {
                    "tipo": mp.get("tipo"),
                    "enunciado": mp.get("enunciado"),
                    "opciones": [
                        {"id": o["id"], "texto": o["texto"]} for o in mp.get("opciones", [])
                    ],
                }

            opcion_correcta = None
            for o in ci.get("micro_pregunta", {}).get("opciones", []):
                if o.get("es_correcta"):
                    opcion_correcta = o["id"]
                    break

            payload_cifrar = {
                "veredictos": ci.get("veredictos"),
                "explicacion": t.explicacion,
                "lineas_infractoras": ci.get("evidencia", {}).get("lineas_infractoras")
                if ci.get("evidencia")
                else None,
                "opcion_correcta_micro_pregunta": opcion_correcta,
            }
            payload_bytes = json.dumps(payload_cifrar).encode("utf-8")
            cifrado_bytes = cifrar_resolucion(str(datos.id), str(t.id), payload_bytes)
            resolucion_b64 = base64.b64encode(cifrado_bytes).decode("utf-8")

            paquete_tarjetas.append(
                PaqueteTarjeta(
                    orden=idx,
                    tarjeta_id=t.id,
                    version=t.version,
                    tipo=t.tipo.value,
                    categoria=t.categoria,
                    personaje_nombre=t.personaje_nombre,
                    personaje_rol=t.personaje_rol,
                    iniciales=t.iniciales,
                    texto=t.texto,
                    evidencia=ev_claro,
                    micro_pregunta=mp_claro,
                    resolucion_cifrada=resolucion_b64,
                )
            )

        intento = Intento(
            id=datos.id,
            usuario_id=usuario_id,
            sprint_id=sprint_id,
            tipo=TipoIntento.sprint,
            estado=EstadoIntento.en_curso,
            ind_presupuesto=sprint.ini_presupuesto,
            ind_reputacion=sprint.ini_reputacion,
            ind_velocidad=sprint.ini_velocidad,
            ind_riesgo=sprint.ini_riesgo,
            hp_jefe=None,
            aciertos=0,
            parciales=0,
            errores=0,
            xp_ganada=0,
            monedas_ganadas=0,
            tarjetas_asignadas=tarjetas_asignadas,
            marcado_revision=False,
            pausado_en=None,
            pausa_acumulada_s=0,
        )
        await self._repo.crear_intento(intento)
        await self._s.commit()

        return PaqueteSprintRespuesta(
            intento_id=intento.id,
            clave_intento=clave_intento_b64(str(intento.id)),
            vidas=vidas_efectivas,
            indicadores={
                "presupuesto": intento.ind_presupuesto,
                "reputacion": intento.ind_reputacion,
                "velocidad": intento.ind_velocidad,
                "riesgo_legal": intento.ind_riesgo,
            },
            tarjetas=paquete_tarjetas,
        )

    async def _reconstruir_paquete(self, intento: Intento, usuario: Any) -> PaqueteSprintRespuesta:
        vidas_efectivas, _ = self._calcular_vidas_efectivas(usuario)
        tarjetas_out: list[PaqueteTarjeta] = []
        for item in intento.tarjetas_asignadas:
            t = await self._repo.buscar_tarjeta_version(
                uuid.UUID(str(item["tarjeta_id"])), int(item["version"])
            )
            if t is None:
                continue
            ci = t.contenido_interactivo
            ev_claro = None
            if t.tipo == TipoTarjeta.evidencia and ci.get("evidencia"):
                ev = ci["evidencia"]
                ev_claro = {
                    "formato": ev.get("formato"),
                    "nombre_archivo": ev.get("nombre_archivo"),
                    "contenido_texto": ev.get("contenido_texto"),
                }
            mp_claro = {}
            if ci.get("micro_pregunta"):
                mp = ci["micro_pregunta"]
                mp_claro = {
                    "tipo": mp.get("tipo"),
                    "enunciado": mp.get("enunciado"),
                    "opciones": [
                        {"id": o["id"], "texto": o["texto"]} for o in mp.get("opciones", [])
                    ],
                }
            opcion_correcta = None
            for o in ci.get("micro_pregunta", {}).get("opciones", []):
                if o.get("es_correcta"):
                    opcion_correcta = o["id"]
                    break

            payload_cifrar = {
                "veredictos": ci.get("veredictos"),
                "explicacion": t.explicacion,
                "lineas_infractoras": ci.get("evidencia", {}).get("lineas_infractoras")
                if ci.get("evidencia")
                else None,
                "opcion_correcta_micro_pregunta": opcion_correcta,
            }
            cifrado_bytes = cifrar_resolucion(
                str(intento.id), str(t.id), json.dumps(payload_cifrar).encode("utf-8")
            )
            tarjetas_out.append(
                PaqueteTarjeta(
                    orden=item["orden"],
                    tarjeta_id=t.id,
                    version=t.version,
                    tipo=t.tipo.value,
                    categoria=t.categoria,
                    personaje_nombre=t.personaje_nombre,
                    personaje_rol=t.personaje_rol,
                    iniciales=t.iniciales,
                    texto=t.texto,
                    evidencia=ev_claro,
                    micro_pregunta=mp_claro,
                    resolucion_cifrada=base64.b64encode(cifrado_bytes).decode("utf-8"),
                )
            )

        return PaqueteSprintRespuesta(
            intento_id=intento.id,
            clave_intento=clave_intento_b64(str(intento.id)),
            vidas=vidas_efectivas,
            indicadores={
                "presupuesto": intento.ind_presupuesto,
                "reputacion": intento.ind_reputacion,
                "velocidad": intento.ind_velocidad,
                "riesgo_legal": intento.ind_riesgo,
            },
            tarjetas=tarjetas_out,
        )

    async def enviar_respuesta(
        self, usuario_id: uuid.UUID, intento_id: uuid.UUID, datos: EnviarRespuestaInput
    ) -> RespuestaEnvioRespuesta:
        cfg = get_config()
        ahora = now()

        usuario = await self._repo.buscar_usuario_con_lock(usuario_id)
        if usuario is None or usuario.estado_cuenta != EstadoCuenta.activo:
            raise NoEncontrado()

        resp_existente = await self._repo.buscar_respuesta_por_id(datos.id)
        if resp_existente is not None:
            return await self._armar_respuesta_guardada(resp_existente, usuario)

        intento = await self._repo.buscar_intento_por_id_con_lock(intento_id)
        if intento is None or intento.usuario_id != usuario_id:
            raise NoEncontrado()
        if intento.estado != EstadoIntento.en_curso:
            raise IntentoCerrado()

        asignada = None
        for item in intento.tarjetas_asignadas:
            if str(item["tarjeta_id"]) == str(datos.tarjeta_id):
                asignada = item
                break
        if asignada is None:
            raise PeticionInvalida(detalle={"motivo": "Tarjeta no pertenece al intento."})

        resp_tarjeta = await self._repo.buscar_respuesta_por_tarjeta(intento_id, datos.tarjeta_id)
        if resp_tarjeta is not None:
            raise YaRespondida()

        tarjeta = await self._repo.buscar_tarjeta_version(
            datos.tarjeta_id, int(asignada["version"])
        )
        if tarjeta is None:
            raise NoEncontrado()

        if intento.tipo == TipoIntento.examen:
            return await self._enviar_respuesta_examen(
                usuario, intento, asignada, tarjeta, datos, ahora
            )

        ci = tarjeta.contenido_interactivo
        veredictos = ci.get("veredictos", {})

        if not datos.veredicto or datos.veredicto not in veredictos:
            raise PeticionInvalida(detalle={"motivo": "Veredicto inválido o no reconocido."})

        v_info = veredictos[datos.veredicto]
        res_str = v_info["resultado"]
        res_enum = ResultadoRespuesta(res_str)

        veredicto_correcto = ""
        for k, val in veredictos.items():
            if val.get("resultado") == "correcto":
                veredicto_correcto = k
                break

        d_p = int(v_info.get("d_presupuesto", 0))
        d_r = int(v_info.get("d_reputacion", 0))
        d_v = int(v_info.get("d_velocidad", 0))
        d_g = int(v_info.get("d_riesgo", 0))

        intento.ind_presupuesto = max(0, min(100, intento.ind_presupuesto + d_p))
        intento.ind_reputacion = max(0, min(100, intento.ind_reputacion + d_r))
        intento.ind_velocidad = max(0, min(100, intento.ind_velocidad + d_v))
        intento.ind_riesgo = max(0, min(100, intento.ind_riesgo + d_g))

        xp_tarjeta = 0
        monedas_tarjeta = 0
        bonos: list[str] = []
        por_que_ok = False
        evidencia_ok = False
        justificacion_ok = False

        if res_enum == ResultadoRespuesta.correcto:
            intento.aciertos += 1
            xp_tarjeta = 10 * cfg.MULTIPLICADOR_PUNTAJE
            monedas_tarjeta = 5

            opcion_correcta = None
            for o in ci.get("micro_pregunta", {}).get("opciones", []):
                if o.get("es_correcta"):
                    opcion_correcta = o["id"]
                    break

            if datos.por_que_opcion_id is not None and opcion_correcta is not None:
                if datos.por_que_opcion_id == opcion_correcta:
                    por_que_ok = True
                    xp_tarjeta += 5
                    bonos.append("por_que")

            if tarjeta.tipo == TipoTarjeta.evidencia:
                lineas_inf = set(ci.get("evidencia", {}).get("lineas_infractoras") or [])
                lineas_sub = set(datos.lineas_subrayadas or [])
                if lineas_inf and lineas_inf == lineas_sub:
                    evidencia_ok = True
                    xp_tarjeta += 5
                    bonos.append("evidencia")

            if tarjeta.tipo == TipoTarjeta.justificacion:
                if datos.justificacion_opcion_id is not None and opcion_correcta is not None:
                    if datos.justificacion_opcion_id == opcion_correcta:
                        justificacion_ok = True
                        monedas_tarjeta *= 2
                        bonos.append("justificacion")

        elif res_enum == ResultadoRespuesta.parcial:
            intento.parciales += 1
            xp_tarjeta = 3
            monedas_tarjeta = 0
        else:
            intento.errores += 1
            xp_tarjeta = 0
            monedas_tarjeta = 0

        sprint = await self._repo.buscar_sprint(intento.sprint_id)
        monedas_max_sprint = sprint.monedas_max if sprint else 60
        monedas_tarjeta = min(monedas_tarjeta, max(0, monedas_max_sprint - intento.monedas_ganadas))

        intento.xp_ganada += xp_tarjeta
        intento.monedas_ganadas += monedas_tarjeta

        vidas_delta = 0
        amparo_usado = False
        if res_enum == ResultadoRespuesta.incorrecto:
            if usuario.amparo_activo:
                usuario.amparo_activo = False
                amparo_usado = True
                vidas_delta = 0
            else:
                vidas_delta = -1
                vidas_base, _ = self._calcular_vidas_efectivas(usuario)
                usuario.vidas = max(0, vidas_base - 1)
                if vidas_base == cfg.VIDAS_MAX:
                    usuario.vidas_base_en = ahora

                await self._repo.crear_movimiento_economia(
                    MovimientoEconomia(
                        usuario_id=usuario_id,
                        recurso="vidas",
                        cantidad=-1,
                        saldo_resultante=usuario.vidas,
                        motivo="error_tarjeta",
                        detalle={"tarjeta_id": str(tarjeta.id)},
                        referencia_id=intento.id,
                    )
                )

                apel_existente = await self._repo.buscar_apelacion_pendiente(usuario_id, tarjeta.id)
                if apel_existente is None:
                    apelacion = Apelacion(
                        id=uuid.uuid4(),
                        usuario_id=usuario_id,
                        tarjeta_id=tarjeta.id,
                        tarjeta_version=tarjeta.version,
                        respuesta_origen_id=datos.id,
                        estado=EstadoApelacion.pendiente,
                        etapa=1,
                        proxima_revision=ahora + timedelta(days=cfg.APELACION_DIAS[0]),
                    )
                    await self._repo.crear_apelacion(apelacion)

        respuesta = Respuesta(
            id=datos.id,
            intento_id=intento_id,
            tarjeta_id=datos.tarjeta_id,
            veredicto=Veredicto(datos.veredicto),
            resultado=res_enum,
            segundos=datos.segundos,
            por_que_ok=por_que_ok,
            evidencia_ok=evidencia_ok,
            justificacion_ok=justificacion_ok,
            contraargumento_ok=None,
            amparo_usado=amparo_usado,
            d_presupuesto=d_p,
            d_reputacion=d_r,
            d_velocidad=d_v,
            d_riesgo=d_g,
            xp=xp_tarjeta,
            monedas=monedas_tarjeta,
            vidas_delta=vidas_delta,
            respondido_en=datos.respondido_en,
            recibido_en=ahora,
        )
        await self._repo.crear_respuesta(respuesta)

        if res_enum == ResultadoRespuesta.correcto and datos.segundos < cfg.SOSPECHA_SEGUNDOS:
            respuestas_previas = await self._repo.listar_respuestas_intento(intento.id)
            rapidas = sum(
                1
                for r in respuestas_previas
                if r.resultado == ResultadoRespuesta.correcto
                and r.segundos
                and float(r.segundos) < cfg.SOSPECHA_SEGUNDOS
            )
            if rapidas + 1 >= cfg.SOSPECHA_MIN_ACIERTOS:
                intento.marcado_revision = True

        await self._avanzar_reto_diario_respuesta(
            usuario, res_enum, por_que_ok, datos.lineas_subrayadas
        )

        total_respuestas = await self._repo.contar_respuestas_intento(intento_id) + 1
        cierre = None
        siguiente_orden = asignada["orden"] + 1 if asignada["orden"] < 10 else None

        if intento.ind_riesgo >= 100 or intento.ind_presupuesto <= 0:
            cierre = await self._cerrar_intento_quebrado(intento, usuario, ahora)
            siguiente_orden = None
        elif total_respuestas >= 10:
            cierre = await self._cerrar_intento_completado(intento, usuario, sprint, ahora)
            siguiente_orden = None

        await self._s.commit()

        vidas_actuales, _ = self._calcular_vidas_efectivas(usuario)

        return RespuestaEnvioRespuesta(
            resultado=res_str,
            veredicto_correcto=veredicto_correcto,
            explicacion=tarjeta.explicacion,
            impacto={
                "presupuesto": d_p,
                "reputacion": d_r,
                "velocidad": d_v,
                "riesgo_legal": d_g,
            },
            indicadores={
                "presupuesto": intento.ind_presupuesto,
                "reputacion": intento.ind_reputacion,
                "velocidad": intento.ind_velocidad,
                "riesgo_legal": intento.ind_riesgo,
            },
            recompensa=RecompensaRespuesta(
                xp=xp_tarjeta,
                monedas=monedas_tarjeta,
                bonos=bonos,
            ),
            vidas=vidas_actuales,
            amparo_usado=amparo_usado,
            estado_intento=intento.estado.value,
            siguiente_orden=siguiente_orden,
            cierre=cierre,
        )

    async def _avanzar_reto_diario_respuesta(
        self,
        usuario: Any,
        resultado: ResultadoRespuesta,
        por_que_ok: bool,
        lineas: list[int] | None,
    ) -> None:
        try:
            reto = RetoDiario.model_validate(usuario.reto_diario)
        except Exception:
            return

        if reto.completado:
            return

        if reto.tipo == "aciertos_seguidos":
            if resultado == ResultadoRespuesta.correcto:
                reto.avance += 1
            else:
                reto.avance = 0
        elif reto.tipo == "por_que_correctos":
            if por_que_ok:
                reto.avance += 1
        elif reto.tipo == "evidencias_inspeccionadas":
            if lineas and len(lineas) > 0:
                reto.avance += 1

        if reto.avance >= reto.meta:
            reto.completado = True
            usuario.monedas += reto.recompensa_monedas
            await self._repo.crear_movimiento_economia(
                MovimientoEconomia(
                    usuario_id=usuario.id,
                    recurso="monedas",
                    cantidad=reto.recompensa_monedas,
                    saldo_resultante=usuario.monedas,
                    motivo="reto_diario",
                    detalle={"tipo": reto.tipo},
                    referencia_id=None,
                )
            )

        usuario.reto_diario = reto.model_dump(mode="json")

    async def _avanzar_reto_diario_sprint(self, usuario: Any) -> None:
        try:
            reto = RetoDiario.model_validate(usuario.reto_diario)
        except Exception:
            return

        if reto.completado:
            return

        if reto.tipo == "sprints_completados":
            reto.avance += 1
            if reto.avance >= reto.meta:
                reto.completado = True
                usuario.monedas += reto.recompensa_monedas
                await self._repo.crear_movimiento_economia(
                    MovimientoEconomia(
                        usuario_id=usuario.id,
                        recurso="monedas",
                        cantidad=reto.recompensa_monedas,
                        saldo_resultante=usuario.monedas,
                        motivo="reto_diario",
                        detalle={"tipo": reto.tipo},
                        referencia_id=None,
                    )
                )

        usuario.reto_diario = reto.model_dump(mode="json")

    def _actualizar_racha(self, usuario: Any, ahora: Any) -> bool:
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
        return bool(usuario.racha_actual >= 7)

    async def _cerrar_intento_quebrado(
        self, intento: Intento, usuario: Any, ahora: Any
    ) -> CierreIntentoRespuesta:
        cfg = get_config()
        intento.estado = EstadoIntento.quebrado
        intento.terminado_en = ahora

        if intento.xp_ganada > 0:
            usuario.xp += intento.xp_ganada
            usuario.nivel = 1 + (usuario.xp // cfg.XP_POR_NIVEL)
            await self._repo.crear_movimiento_economia(
                MovimientoEconomia(
                    usuario_id=usuario.id,
                    recurso="xp",
                    cantidad=intento.xp_ganada,
                    saldo_resultante=usuario.xp,
                    motivo="sprint",
                    detalle={"intento_id": str(intento.id), "estado": "quebrado"},
                    referencia_id=intento.id,
                )
            )

        return CierreIntentoRespuesta(
            estado="quebrado",
            estrellas=0,
            xp_acreditada=intento.xp_ganada,
            monedas_acreditadas=0,
            indicadores={
                "presupuesto": intento.ind_presupuesto,
                "reputacion": intento.ind_reputacion,
                "velocidad": intento.ind_velocidad,
                "riesgo_legal": intento.ind_riesgo,
            },
            insignias_nuevas=[],
        )

    async def _cerrar_intento_completado(
        self, intento: Intento, usuario: Any, sprint: Any, ahora: Any
    ) -> CierreIntentoRespuesta:
        cfg = get_config()
        intento.estado = EstadoIntento.completado
        intento.terminado_en = ahora

        estrellas = 1
        if intento.aciertos == 10 and intento.parciales == 0 and intento.errores == 0:
            estrellas = 3
        elif intento.aciertos in (8, 9):
            estrellas = 2

        if intento.xp_ganada > 0:
            usuario.xp += intento.xp_ganada
            usuario.nivel = 1 + (usuario.xp // cfg.XP_POR_NIVEL)
            await self._repo.crear_movimiento_economia(
                MovimientoEconomia(
                    usuario_id=usuario.id,
                    recurso="xp",
                    cantidad=intento.xp_ganada,
                    saldo_resultante=usuario.xp,
                    motivo="sprint",
                    detalle={"intento_id": str(intento.id), "estado": "completado"},
                    referencia_id=intento.id,
                )
            )

        if intento.monedas_ganadas > 0:
            usuario.monedas += intento.monedas_ganadas
            await self._repo.crear_movimiento_economia(
                MovimientoEconomia(
                    usuario_id=usuario.id,
                    recurso="monedas",
                    cantidad=intento.monedas_ganadas,
                    saldo_resultante=usuario.monedas,
                    motivo="sprint",
                    detalle={"intento_id": str(intento.id), "estado": "completado"},
                    referencia_id=intento.id,
                )
            )

        prog = await self._repo.buscar_progreso(usuario.id, intento.sprint_id)
        if prog:
            prog.estado = EstadoProgreso.completado
            prog.estrellas = max(prog.estrellas, estrellas)
            prog.mejor_aciertos = max(prog.mejor_aciertos, intento.aciertos)
            if estrellas == 3:
                prog.perfecto = True
            prog.completado_en = ahora

        if sprint:
            await self._repo.desbloquear_siguiente_sprint(
                usuario.id, sprint.modulo_id, sprint.orden + 1
            )

        insignias_nuevas: list[str] = []
        if await self._repo.otorgar_insignia(usuario.id, "primer_sprint"):
            insignias_nuevas.append("primer_sprint")
        if estrellas == 3:
            if await self._repo.otorgar_insignia(usuario.id, "sprint_perfecto"):
                insignias_nuevas.append("sprint_perfecto")

        await self._avanzar_reto_diario_sprint(usuario)

        if self._actualizar_racha(usuario, ahora):
            if await self._repo.otorgar_insignia(usuario.id, "racha_7"):
                insignias_nuevas.append("racha_7")

        return CierreIntentoRespuesta(
            estado="completado",
            estrellas=estrellas,
            xp_acreditada=intento.xp_ganada,
            monedas_acreditadas=intento.monedas_ganadas,
            indicadores={
                "presupuesto": intento.ind_presupuesto,
                "reputacion": intento.ind_reputacion,
                "velocidad": intento.ind_velocidad,
                "riesgo_legal": intento.ind_riesgo,
            },
            insignias_nuevas=insignias_nuevas,
        )

    async def _armar_respuesta_guardada(
        self, resp: Respuesta, usuario: Any
    ) -> RespuestaEnvioRespuesta:
        intento = await self._repo.buscar_intento_por_id(resp.intento_id)
        ver = 1
        if intento and isinstance(intento.tarjetas_asignadas, list):
            for item in intento.tarjetas_asignadas:
                if str(item.get("tarjeta_id")) == str(resp.tarjeta_id):
                    ver = int(item.get("version", 1))
                    break
        tarjeta = await self._repo.buscar_tarjeta_version(resp.tarjeta_id, ver)
        vidas, _ = self._calcular_vidas_efectivas(usuario)

        veredicto_correcto = ""
        if tarjeta and isinstance(tarjeta.contenido_interactivo, dict):
            veredictos = tarjeta.contenido_interactivo.get("veredictos", {})
            for k, val in veredictos.items():
                if val.get("resultado") == "correcto":
                    veredicto_correcto = k
                    break

        return RespuestaEnvioRespuesta(
            resultado=resp.resultado.value,
            veredicto_correcto=veredicto_correcto,
            explicacion=tarjeta.explicacion if tarjeta else "",
            impacto={
                "presupuesto": resp.d_presupuesto,
                "reputacion": resp.d_reputacion,
                "velocidad": resp.d_velocidad,
                "riesgo_legal": resp.d_riesgo,
            },
            indicadores={
                "presupuesto": intento.ind_presupuesto if intento else 70,
                "reputacion": intento.ind_reputacion if intento else 60,
                "velocidad": intento.ind_velocidad if intento else 50,
                "riesgo_legal": intento.ind_riesgo if intento else 25,
            },
            recompensa=RecompensaRespuesta(
                xp=resp.xp,
                monedas=resp.monedas,
                bonos=[],
            ),
            vidas=vidas,
            amparo_usado=resp.amparo_usado,
            estado_intento=intento.estado.value if intento else "en_curso",
            siguiente_orden=None,
            cierre=None,
        )

    async def obtener_intento(
        self, usuario_id: uuid.UUID, intento_id: uuid.UUID
    ) -> EstadoIntentoRespuesta:
        intento = await self._repo.buscar_intento_por_id(intento_id)
        if intento is None or intento.usuario_id != usuario_id:
            raise NoEncontrado()

        usuario = await self._repo.buscar_usuario_con_lock(usuario_id)
        vidas, _ = self._calcular_vidas_efectivas(usuario) if usuario else (5, None)
        total_respuestas = await self._repo.contar_respuestas_intento(intento_id)
        total_tarjetas = (
            len(intento.tarjetas_asignadas) if isinstance(intento.tarjetas_asignadas, list) else 10
        )

        return EstadoIntentoRespuesta(
            id=intento.id,
            sprint_id=intento.sprint_id,
            tipo=intento.tipo.value,
            estado=intento.estado.value,
            vidas=vidas,
            indicadores={
                "presupuesto": intento.ind_presupuesto,
                "reputacion": intento.ind_reputacion,
                "velocidad": intento.ind_velocidad,
                "riesgo_legal": intento.ind_riesgo,
            },
            respuestas_completadas=total_respuestas,
            total_tarjetas=total_tarjetas,
            xp_ganada=intento.xp_ganada,
            monedas_ganadas=intento.monedas_ganadas,
            clave_intento=clave_intento_b64(str(intento.id)),
        )

    async def abandonar_intento(
        self, usuario_id: uuid.UUID, intento_id: uuid.UUID
    ) -> AbandonarRespuesta:
        intento = await self._repo.buscar_intento_por_id_con_lock(intento_id)
        if intento is None or intento.usuario_id != usuario_id:
            raise NoEncontrado()
        if intento.estado != EstadoIntento.en_curso:
            raise IntentoCerrado()

        intento.estado = EstadoIntento.abandonado
        intento.terminado_en = now()
        await self._s.commit()

        return AbandonarRespuesta(
            id=intento.id,
            estado="abandonado",
            mensaje="El intento ha sido abandonado sin acreditación de puntos.",
        )

    async def usar_comodin(
        self, usuario_id: uuid.UUID, intento_id: uuid.UUID, datos: UsarComodinInput
    ) -> UsarComodinRespuesta:
        usuario = await self._repo.buscar_usuario_con_lock(usuario_id)
        if usuario is None or usuario.estado_cuenta != EstadoCuenta.activo:
            raise NoEncontrado()

        intento = await self._repo.buscar_intento_por_id_con_lock(intento_id)
        if intento is None or intento.usuario_id != usuario_id:
            raise NoEncontrado()

        if intento.tipo != TipoIntento.sprint:
            raise SinPermiso(detalle={"motivo": "Comodines no permitidos en este tipo de intento."})

        if intento.estado != EstadoIntento.en_curso:
            raise IntentoCerrado()

        inv = Inventario.model_validate(usuario.inventario)
        cant = getattr(inv, datos.comodin, 0)
        if cant <= 0:
            raise SaldoInsuficiente(detalle={"comodin": datos.comodin})

        if datos.comodin == "amparo":
            if usuario.amparo_activo:
                raise ComodinYaUsado()
            usuario.amparo_activo = True
            setattr(inv, "amparo", cant - 1)
            usuario.inventario = inv.model_dump()
            await self._s.commit()
            return UsarComodinRespuesta(
                comodin="amparo",
                efecto={"amparo_activo": True},
                inventario=usuario.inventario,
                amparo_activo=True,
            )

        if datos.tarjeta_orden is None:
            raise PeticionInvalida(
                detalle={"motivo": "tarjeta_orden es requerido para este comodin."}
            )

        tarjetas_lista = list(intento.tarjetas_asignadas)
        asignada = None
        for item in tarjetas_lista:
            if item.get("orden") == datos.tarjeta_orden:
                asignada = item
                break

        if asignada is None:
            raise PeticionInvalida(detalle={"motivo": "Tarjeta no encontrada en el intento."})

        comodines_usados = list(asignada.get("comodines", []))
        if datos.comodin in comodines_usados:
            raise ComodinYaUsado()

        tarjeta = await self._repo.buscar_tarjeta_version(
            uuid.UUID(str(asignada["tarjeta_id"])), int(asignada["version"])
        )
        if tarjeta is None:
            raise NoEncontrado()

        setattr(inv, datos.comodin, cant - 1)
        usuario.inventario = inv.model_dump()

        comodines_usados.append(datos.comodin)
        asignada["comodines"] = comodines_usados
        intento.tarjetas_asignadas = tarjetas_lista

        if datos.comodin == "lupa":
            palabras = tarjeta.array_palabras_trampa or []
            efecto = {"palabras_trampa": palabras, "array_palabras_trampa": palabras}
        else:
            nota = tarjeta.nota_abogado or ""
            efecto = {"nota_abogado": nota}

        await self._s.commit()

        return UsarComodinRespuesta(
            comodin=datos.comodin,
            efecto=efecto,
            inventario=usuario.inventario,
            amparo_activo=usuario.amparo_activo,
        )

    def _armar_decision_examen(
        self, item: dict[str, Any], tarjeta: Any, escenario: dict[str, Any], preferencias: Any
    ) -> DecisionExamen:
        cfg = get_config()
        seg_base = escenario.get("segundos_decision", 15)
        tiempo_ext = (
            preferencias.get("tiempo_extendido", False) if isinstance(preferencias, dict) else False
        )
        segundos_limite = float(
            seg_base * (1.5 if tiempo_ext else 1.0) + cfg.EXAMEN_TOLERANCIA_RED_S
        )

        ci = tarjeta.contenido_interactivo if tarjeta else {}
        ev_claro = None
        if ci.get("evidencia"):
            ev = ci["evidencia"]
            ev_claro = {
                "formato": ev.get("formato"),
                "nombre_archivo": ev.get("nombre_archivo"),
                "contenido_texto": ev.get("contenido_texto"),
            }

        t_dict = {
            "id": str(tarjeta.id) if tarjeta else str(item["tarjeta_id"]),
            "version": tarjeta.version if tarjeta else item["version"],
            "tipo": tarjeta.tipo.value
            if hasattr(tarjeta.tipo, "value")
            else str(tarjeta.tipo)
            if tarjeta
            else "normal",
            "categoria": tarjeta.categoria if tarjeta else "",
            "personaje_nombre": tarjeta.personaje_nombre if tarjeta else "",
            "personaje_rol": tarjeta.personaje_rol if tarjeta else "",
            "iniciales": tarjeta.iniciales if tarjeta else "",
            "texto": tarjeta.texto if tarjeta else "",
            "evidencia": ev_claro,
        }

        return DecisionExamen(
            orden=item["orden"],
            hora_crisis=item.get("hora_crisis", 0),
            tarjeta=t_dict,
            segundos_limite=segundos_limite,
        )

    async def _cerrar_examen_aprobado(
        self, intento: Intento, usuario: Any, sprint: Any, ahora: Any
    ) -> CierreIntentoRespuesta:
        cfg = get_config()
        intento.estado = EstadoIntento.completado
        intento.terminado_en = ahora

        if intento.xp_ganada > 0:
            usuario.xp += intento.xp_ganada
            usuario.nivel = 1 + (usuario.xp // cfg.XP_POR_NIVEL)
            await self._repo.crear_movimiento_economia(
                MovimientoEconomia(
                    usuario_id=usuario.id,
                    recurso="xp",
                    cantidad=intento.xp_ganada,
                    saldo_resultante=usuario.xp,
                    motivo="examen",
                    detalle={"intento_id": str(intento.id), "estado": "aprobado"},
                    referencia_id=intento.id,
                )
            )

        if intento.monedas_ganadas > 0:
            usuario.monedas += intento.monedas_ganadas
            await self._repo.crear_movimiento_economia(
                MovimientoEconomia(
                    usuario_id=usuario.id,
                    recurso="monedas",
                    cantidad=intento.monedas_ganadas,
                    saldo_resultante=usuario.monedas,
                    motivo="examen",
                    detalle={"intento_id": str(intento.id), "estado": "aprobado"},
                    referencia_id=intento.id,
                )
            )

        modulo = await self._repo.buscar_modulo(sprint.modulo_id) if sprint else None
        seq = await self._repo.obtener_siguiente_folio_seq()
        num_mod = modulo.numero if modulo else 1
        folio = f"AG-{ahora.year}-{num_mod}-{seq:06d}"

        cert = Certificado(
            usuario_id=usuario.id,
            modulo_id=sprint.modulo_id if sprint else 1,
            intento_id=intento.id,
            folio=folio,
            emitido_en=ahora,
        )
        await self._repo.crear_certificado(cert)

        prog = await self._repo.buscar_progreso(usuario.id, intento.sprint_id)
        if prog:
            prog.estado = EstadoProgreso.completado
            prog.estrellas = 3
            prog.perfecto = True
            prog.completado_en = ahora

        if modulo:
            await self._repo.desbloquear_siguiente_modulo(usuario.id, modulo.numero + 1)

        insignias_nuevas: list[str] = []
        if self._actualizar_racha(usuario, ahora):
            if await self._repo.otorgar_insignia(usuario.id, "racha_7"):
                insignias_nuevas.append("racha_7")

        if await self._repo.otorgar_insignia(usuario.id, "modulo_aprobado"):
            insignias_nuevas.append("modulo_aprobado")

        return CierreIntentoRespuesta(
            estado="completado",
            estrellas=3,
            xp_acreditada=intento.xp_ganada or 0,
            monedas_acreditadas=intento.monedas_ganadas or 0,
            indicadores={
                "presupuesto": intento.ind_presupuesto or 70,
                "reputacion": intento.ind_reputacion or 60,
                "velocidad": intento.ind_velocidad or 50,
                "riesgo_legal": intento.ind_riesgo or 25,
            },
            insignias_nuevas=insignias_nuevas,
        )

    async def _cerrar_examen_reprobado(
        self, intento: Intento, usuario: Any, ahora: Any
    ) -> CierreIntentoRespuesta:
        cfg = get_config()
        intento.estado = EstadoIntento.reprobado
        intento.terminado_en = ahora

        if intento.xp_ganada > 0:
            usuario.xp += intento.xp_ganada
            usuario.nivel = 1 + (usuario.xp // cfg.XP_POR_NIVEL)
            await self._repo.crear_movimiento_economia(
                MovimientoEconomia(
                    usuario_id=usuario.id,
                    recurso="xp",
                    cantidad=intento.xp_ganada,
                    saldo_resultante=usuario.xp,
                    motivo="examen",
                    detalle={"intento_id": str(intento.id), "estado": "reprobado"},
                    referencia_id=intento.id,
                )
            )

        return CierreIntentoRespuesta(
            estado="reprobado",
            estrellas=0,
            xp_acreditada=intento.xp_ganada or 0,
            monedas_acreditadas=0,
            indicadores={
                "presupuesto": intento.ind_presupuesto or 70,
                "reputacion": intento.ind_reputacion or 60,
                "velocidad": intento.ind_velocidad or 50,
                "riesgo_legal": intento.ind_riesgo or 25,
            },
            insignias_nuevas=[],
        )

    async def _enviar_respuesta_examen(
        self,
        usuario: Any,
        intento: Intento,
        asignada: dict[str, Any],
        tarjeta: Tarjeta,
        datos: EnviarRespuestaInput,
        ahora: Any,
    ) -> RespuestaEnvioRespuesta:
        cfg = get_config()
        if intento.pausado_en is not None:
            raise PeticionInvalida(detalle={"motivo": "Examen actualmente pausado."})

        respuestas_previas = await self._repo.listar_respuestas_intento(intento.id)
        for r in respuestas_previas:
            if r.resultado == ResultadoRespuesta.correcto and r.contraargumento_ok is None:
                raise PeticionInvalida(detalle={"motivo": "Contraargumento previo pendiente."})

        ci = tarjeta.contenido_interactivo
        veredictos = ci.get("veredictos", {})
        if not datos.veredicto or datos.veredicto not in veredictos:
            raise PeticionInvalida(detalle={"motivo": "Veredicto inválido o no reconocido."})

        v_info = veredictos[datos.veredicto]
        veredicto_correcto = ""
        for k, val in veredictos.items():
            if val.get("resultado") == "correcto":
                veredicto_correcto = k
                break

        sprint = await self._repo.buscar_sprint(intento.sprint_id)
        escenario = sprint.escenario_jefe if sprint and sprint.escenario_jefe else {}
        seg_base = escenario.get("segundos_decision", 15)
        tiempo_ext = (
            usuario.preferencias.get("tiempo_extendido", False)
            if isinstance(usuario.preferencias, dict)
            else False
        )
        limite_s = (seg_base * (1.5 if tiempo_ext else 1.0)) + cfg.EXAMEN_TOLERANCIA_RED_S

        if asignada.get("entregada_en"):
            entregada_dt = datetime.fromisoformat(asignada["entregada_en"])
            pausa_s = asignada.get("pausa_s", 0)
            elapsed = (ahora - entregada_dt).total_seconds() - pausa_s
        else:
            elapsed = datos.segundos

        if elapsed > limite_s:
            res_str = "tiempo_agotado"
            res_enum = ResultadoRespuesta.tiempo_agotado
        else:
            res_str = v_info["resultado"]
            res_enum = ResultadoRespuesta(res_str)

        xp_tarjeta = 0
        monedas_tarjeta = 0
        vidas_delta = 0

        tarjetas_lista = list(intento.tarjetas_asignadas)
        asignada_en_lista = None
        for item in tarjetas_lista:
            if item.get("orden") == asignada["orden"]:
                asignada_en_lista = item
                break
        if asignada_en_lista is None:
            asignada_en_lista = asignada

        siguiente_orden = None
        cierre = None

        if res_enum == ResultadoRespuesta.correcto:
            intento.aciertos = (intento.aciertos or 0) + 1
            xp_tarjeta = 10 * cfg.MULTIPLICADOR_PUNTAJE
            monedas_tarjeta = 5
            asignada_en_lista["contra_entregada_en"] = ahora.isoformat()
        elif res_enum == ResultadoRespuesta.parcial:
            intento.parciales = (intento.parciales or 0) + 1
            sig = next((d for d in tarjetas_lista if d["orden"] == asignada["orden"] + 1), None)
            if sig:
                sig["entregada_en"] = ahora.isoformat()
                siguiente_orden = sig["orden"]
            else:
                if (intento.hp_jefe or 0) > 0:
                    cierre = await self._cerrar_examen_reprobado(intento, usuario, ahora)
        else:
            intento.errores = (intento.errores or 0) + 1
            vidas_delta = -1
            vidas_base, _ = self._calcular_vidas_efectivas(usuario)
            usuario.vidas = max(0, vidas_base - 1)
            if vidas_base == cfg.VIDAS_MAX:
                usuario.vidas_base_en = ahora

            await self._repo.crear_movimiento_economia(
                MovimientoEconomia(
                    usuario_id=usuario.id,
                    recurso="vidas",
                    cantidad=-1,
                    saldo_resultante=usuario.vidas,
                    motivo="error_examen",
                    detalle={"tarjeta_id": str(tarjeta.id)},
                    referencia_id=intento.id,
                )
            )

            if usuario.vidas == 0:
                cierre = await self._cerrar_examen_reprobado(intento, usuario, ahora)
            else:
                sig = next((d for d in tarjetas_lista if d["orden"] == asignada["orden"] + 1), None)
                if sig:
                    sig["entregada_en"] = ahora.isoformat()
                    siguiente_orden = sig["orden"]
                else:
                    if (intento.hp_jefe or 0) > 0:
                        cierre = await self._cerrar_examen_reprobado(intento, usuario, ahora)

        intento.tarjetas_asignadas = tarjetas_lista
        intento.xp_ganada = (intento.xp_ganada or 0) + xp_tarjeta
        intento.monedas_ganadas = (intento.monedas_ganadas or 0) + monedas_tarjeta

        respuesta = Respuesta(
            id=datos.id,
            intento_id=intento.id,
            tarjeta_id=datos.tarjeta_id,
            veredicto=Veredicto(datos.veredicto),
            resultado=res_enum,
            segundos=datos.segundos,
            por_que_ok=False,
            evidencia_ok=False,
            justificacion_ok=False,
            contraargumento_ok=None,
            amparo_usado=False,
            d_presupuesto=0,
            d_reputacion=0,
            d_velocidad=0,
            d_riesgo=0,
            xp=xp_tarjeta,
            monedas=monedas_tarjeta,
            vidas_delta=vidas_delta,
            respondido_en=datos.respondido_en,
            recibido_en=ahora,
        )
        await self._repo.crear_respuesta(respuesta)
        await self._s.commit()

        vidas_actuales, _ = self._calcular_vidas_efectivas(usuario)

        return RespuestaEnvioRespuesta(
            resultado=res_str,
            veredicto_correcto=veredicto_correcto,
            explicacion=tarjeta.explicacion,
            impacto={"presupuesto": 0, "reputacion": 0, "velocidad": 0, "riesgo_legal": 0},
            indicadores={
                "presupuesto": intento.ind_presupuesto,
                "reputacion": intento.ind_reputacion,
                "velocidad": intento.ind_velocidad,
                "riesgo_legal": intento.ind_riesgo,
            },
            recompensa=RecompensaRespuesta(
                xp=xp_tarjeta,
                monedas=monedas_tarjeta,
                bonos=[],
            ),
            vidas=vidas_actuales,
            amparo_usado=False,
            estado_intento=intento.estado.value,
            siguiente_orden=siguiente_orden,
            cierre=cierre,
        )

    async def iniciar_examen(
        self, usuario_id: uuid.UUID, sprint_id: int, datos: IniciarExamenInput
    ) -> IniciarExamenRespuesta:
        ahora = now()

        usuario = await self._repo.buscar_usuario_con_lock(usuario_id)
        if usuario is None or usuario.estado_cuenta != EstadoCuenta.activo:
            raise NoEncontrado()

        existente = await self._repo.buscar_intento_por_id(datos.id)
        if existente is not None and existente.usuario_id == usuario_id:
            return await self._reconstruir_examen(existente, usuario)

        vidas_efectivas, proxima_en = self._calcular_vidas_efectivas(usuario)
        if vidas_efectivas <= 0:
            raise SinVidas(
                detalle={"proxima_vida_en": proxima_en.isoformat() if proxima_en else None}
            )

        sprint = await self._repo.buscar_sprint(sprint_id)
        if sprint is None or not sprint.es_examen:
            raise SprintBloqueado()

        escenario = sprint.escenario_jefe
        if not escenario or not isinstance(escenario, dict) or not escenario.get("decisiones"):
            raise SprintBloqueado(detalle={"motivo": "escenario_no_cargado"})

        completados = await self._repo.contar_sprints_completados_modulo(
            usuario_id, sprint.modulo_id
        )
        if completados < 5:
            raise SprintBloqueado(detalle={"motivo": "sprints_previos_incompletos"})

        cert = await self._repo.buscar_certificado(usuario_id, sprint.modulo_id)
        if cert is not None:
            raise SprintBloqueado(detalle={"motivo": "examen_ya_aprobado"})

        en_curso = await self._repo.buscar_intento_en_curso(usuario_id)
        if en_curso is not None:
            raise IntentoEnCurso(detalle={"intento_id": str(en_curso.id)})

        decisiones_raw = list(escenario["decisiones"])
        grupos: dict[int, list[dict[str, Any]]] = {0: [], 6: [], 24: [], 72: []}
        for d in decisiones_raw:
            hc = d.get("hora_crisis", 0)
            if hc in grupos:
                grupos[hc].append(d)
            else:
                grupos.setdefault(hc, []).append(d)

        decisiones_ordenadas: list[dict[str, Any]] = []
        for hc in (0, 6, 24, 72):
            if hc in grupos:
                sub = list(grupos[hc])
                random.shuffle(sub)
                decisiones_ordenadas.extend(sub)

        tarjetas_asignadas: list[dict[str, Any]] = []
        for idx, d in enumerate(decisiones_ordenadas, start=1):
            tarjetas_asignadas.append(
                {
                    "orden": idx,
                    "tarjeta_id": str(d["tarjeta_id"]),
                    "version": 1,
                    "hora_crisis": d.get("hora_crisis", 0),
                    "replica_jefe": d.get("replica_jefe", ""),
                    "fundamentos": d.get("fundamentos", []),
                    "entregada_en": ahora.isoformat() if idx == 1 else None,
                    "pausa_s": 0,
                    "contra_entregada_en": None,
                    "comodines": [],
                }
            )

        intento = Intento(
            id=datos.id,
            usuario_id=usuario_id,
            sprint_id=sprint_id,
            tipo=TipoIntento.examen,
            estado=EstadoIntento.en_curso,
            ind_presupuesto=sprint.ini_presupuesto,
            ind_reputacion=sprint.ini_reputacion,
            ind_velocidad=sprint.ini_velocidad,
            ind_riesgo=sprint.ini_riesgo,
            hp_jefe=escenario.get("hp_inicial", 100),
            aciertos=0,
            parciales=0,
            errores=0,
            xp_ganada=0,
            monedas_ganadas=0,
            tarjetas_asignadas=tarjetas_asignadas,
            marcado_revision=False,
            pausado_en=None,
            pausa_acumulada_s=0,
        )
        await self._repo.crear_intento(intento)
        await self._s.commit()

        d1 = tarjetas_asignadas[0]
        t1 = await self._repo.buscar_tarjeta_version(uuid.UUID(d1["tarjeta_id"]), d1["version"])
        decision_1 = self._armar_decision_examen(d1, t1, escenario, usuario.preferencias)

        return IniciarExamenRespuesta(
            intento_id=intento.id,
            hp_jefe=intento.hp_jefe or 100,
            vidas=vidas_efectivas,
            titulo_crisis=escenario.get("titulo_crisis", "Crisis"),
            descripcion_crisis=escenario.get("descripcion", ""),
            decision=decision_1,
        )

    async def _reconstruir_examen(self, intento: Intento, usuario: Any) -> IniciarExamenRespuesta:
        vidas_efectivas, _ = self._calcular_vidas_efectivas(usuario)
        sprint = await self._repo.buscar_sprint(intento.sprint_id)
        escenario = sprint.escenario_jefe if sprint and sprint.escenario_jefe else {}
        d1 = intento.tarjetas_asignadas[0]
        t1 = await self._repo.buscar_tarjeta_version(uuid.UUID(d1["tarjeta_id"]), d1["version"])
        decision_1 = self._armar_decision_examen(d1, t1, escenario, usuario.preferencias)

        return IniciarExamenRespuesta(
            intento_id=intento.id,
            hp_jefe=intento.hp_jefe or 100,
            vidas=vidas_efectivas,
            titulo_crisis=escenario.get("titulo_crisis", "Crisis"),
            descripcion_crisis=escenario.get("descripcion", ""),
            decision=decision_1,
        )

    async def responder_contraargumento(
        self, usuario_id: uuid.UUID, intento_id: uuid.UUID, datos: ContraargumentoInput
    ) -> ContraargumentoRespuesta:
        cfg = get_config()
        ahora = now()

        usuario = await self._repo.buscar_usuario_con_lock(usuario_id)
        if usuario is None or usuario.estado_cuenta != EstadoCuenta.activo:
            raise NoEncontrado()

        intento = await self._repo.buscar_intento_por_id_con_lock(intento_id)
        if intento is None or intento.usuario_id != usuario_id:
            raise NoEncontrado()

        if intento.tipo != TipoIntento.examen:
            raise SinPermiso()

        if intento.estado != EstadoIntento.en_curso:
            raise IntentoCerrado()

        if intento.pausado_en is not None:
            raise PeticionInvalida(detalle={"motivo": "Examen en pausa"})

        resp = await self._repo.buscar_respuesta_por_id(datos.respuesta_id)
        if resp is None or resp.intento_id != intento_id:
            raise NoEncontrado()

        if resp.contraargumento_ok is not None:
            vidas_act, _ = self._calcular_vidas_efectivas(usuario)
            return ContraargumentoRespuesta(
                hp_jefe=intento.hp_jefe or 0,
                vidas=vidas_act,
                contraargumento_ok=resp.contraargumento_ok,
                siguiente_decision=None,
                cierre=None,
            )

        tarjetas_lista = list(intento.tarjetas_asignadas)
        asignada = None
        for item in tarjetas_lista:
            if str(item.get("tarjeta_id")) == str(resp.tarjeta_id):
                asignada = item
                break

        if asignada is None:
            raise PeticionInvalida(detalle={"motivo": "Tarjeta no encontrada"})

        sprint = await self._repo.buscar_sprint(intento.sprint_id)
        escenario = sprint.escenario_jefe if sprint and sprint.escenario_jefe else {}
        seg_base = escenario.get("segundos_contraargumento", 8)
        tiempo_ext = (
            usuario.preferencias.get("tiempo_extendido", False)
            if isinstance(usuario.preferencias, dict)
            else False
        )
        limite_s = (seg_base * (1.5 if tiempo_ext else 1.0)) + 2.0

        if asignada.get("contra_entregada_en"):
            contra_dt = datetime.fromisoformat(asignada["contra_entregada_en"])
            elapsed = (ahora - contra_dt).total_seconds()
        else:
            elapsed = 0.0

        fundamentos = asignada.get("fundamentos", [])
        fund = next((f for f in fundamentos if f.get("id") == datos.fundamento_id), None)
        if fund is None:
            raise PeticionInvalida(detalle={"motivo": "Fundamento no válido."})

        es_correcto = bool(fund.get("es_correcta") and elapsed <= limite_s)

        cierre = None
        siguiente_decision = None

        if es_correcto:
            resp.contraargumento_ok = True
            dano = int(escenario.get("dano_por_golpe", 20))
            intento.hp_jefe = max(0, (intento.hp_jefe or 100) - dano)
        else:
            resp.contraargumento_ok = False
            vidas_base, _ = self._calcular_vidas_efectivas(usuario)
            usuario.vidas = max(0, vidas_base - 1)
            if vidas_base == cfg.VIDAS_MAX:
                usuario.vidas_base_en = ahora

            await self._repo.crear_movimiento_economia(
                MovimientoEconomia(
                    usuario_id=usuario.id,
                    recurso="vidas",
                    cantidad=-1,
                    saldo_resultante=usuario.vidas,
                    motivo="error_contraargumento",
                    detalle={"intento_id": str(intento.id)},
                    referencia_id=intento.id,
                )
            )

        if intento.hp_jefe == 0:
            cierre = await self._cerrar_examen_aprobado(intento, usuario, sprint, ahora)
        elif usuario.vidas == 0:
            cierre = await self._cerrar_examen_reprobado(intento, usuario, ahora)
        else:
            sig = next((d for d in tarjetas_lista if d["orden"] == asignada["orden"] + 1), None)
            if sig:
                sig["entregada_en"] = ahora.isoformat()
                t_sig = await self._repo.buscar_tarjeta_version(
                    uuid.UUID(sig["tarjeta_id"]), sig["version"]
                )
                siguiente_decision = self._armar_decision_examen(
                    sig, t_sig, escenario, usuario.preferencias
                )
            else:
                if (intento.hp_jefe or 0) > 0:
                    cierre = await self._cerrar_examen_reprobado(intento, usuario, ahora)

        intento.tarjetas_asignadas = tarjetas_lista
        await self._s.commit()

        vidas_final, _ = self._calcular_vidas_efectivas(usuario)
        return ContraargumentoRespuesta(
            hp_jefe=intento.hp_jefe or 0,
            vidas=vidas_final,
            contraargumento_ok=es_correcto,
            siguiente_decision=siguiente_decision,
            cierre=cierre,
        )

    async def pausar_examen(self, usuario_id: uuid.UUID, intento_id: uuid.UUID) -> PausaRespuesta:
        usuario = await self._repo.buscar_usuario_con_lock(usuario_id)
        if usuario is None:
            raise NoEncontrado()

        tiempo_ext = (
            usuario.preferencias.get("tiempo_extendido", False)
            if isinstance(usuario.preferencias, dict)
            else False
        )
        if not tiempo_ext:
            raise PausaNoPermitida()

        intento = await self._repo.buscar_intento_por_id_con_lock(intento_id)
        if intento is None or intento.usuario_id != usuario_id:
            raise NoEncontrado()

        if intento.tipo != TipoIntento.examen or intento.estado != EstadoIntento.en_curso:
            raise PeticionInvalida(detalle={"motivo": "No se puede pausar este intento."})

        if intento.pausado_en is not None:
            raise PeticionInvalida(detalle={"motivo": "El intento ya está pausado."})

        ahora = now()
        intento.pausado_en = ahora
        await self._s.commit()

        return PausaRespuesta(
            pausado=True,
            pausado_en=ahora,
            pausa_acumulada_s=intento.pausa_acumulada_s or 0,
        )

    async def reanudar_examen(
        self, usuario_id: uuid.UUID, intento_id: uuid.UUID
    ) -> ReanudarRespuesta:
        cfg = get_config()
        ahora = now()

        usuario = await self._repo.buscar_usuario_con_lock(usuario_id)
        if usuario is None:
            raise NoEncontrado()

        intento = await self._repo.buscar_intento_por_id_con_lock(intento_id)
        if intento is None or intento.usuario_id != usuario_id:
            raise NoEncontrado()

        if intento.tipo != TipoIntento.examen or intento.estado != EstadoIntento.en_curso:
            raise PeticionInvalida(detalle={"motivo": "Intento no válido."})

        if intento.pausado_en is None:
            raise PeticionInvalida(detalle={"motivo": "El intento no está pausado."})

        dur = int((ahora - intento.pausado_en).total_seconds())
        if (intento.pausa_acumulada_s or 0) + dur > cfg.EXAMEN_PAUSA_MAX_S:
            intento.estado = EstadoIntento.abandonado
            intento.terminado_en = ahora
            await self._s.commit()
            raise PausaAgotada()

        intento.pausa_acumulada_s = (intento.pausa_acumulada_s or 0) + dur
        intento.pausado_en = None

        sprint = await self._repo.buscar_sprint(intento.sprint_id)
        escenario = sprint.escenario_jefe if sprint and sprint.escenario_jefe else {}
        tarjetas_lista = list(intento.tarjetas_asignadas)

        activa = None
        for d in tarjetas_lista:
            if d.get("entregada_en"):
                resp = await self._repo.buscar_respuesta_por_tarjeta(
                    intento.id, uuid.UUID(d["tarjeta_id"])
                )
                if resp is None:
                    activa = d
                    break

        if activa is None and len(tarjetas_lista) > 0:
            activa = tarjetas_lista[0]

        if activa:
            activa["pausa_s"] = activa.get("pausa_s", 0) + dur

        intento.tarjetas_asignadas = tarjetas_lista
        await self._s.commit()

        t = (
            await self._repo.buscar_tarjeta_version(
                uuid.UUID(activa["tarjeta_id"]), activa["version"]
            )
            if activa
            else None
        )
        decision = self._armar_decision_examen(activa, t, escenario, usuario.preferencias)

        seg_base = escenario.get("segundos_decision", 15)
        tiempo_ext = (
            usuario.preferencias.get("tiempo_extendido", False)
            if isinstance(usuario.preferencias, dict)
            else False
        )
        limite = (seg_base * (1.5 if tiempo_ext else 1.0)) + cfg.EXAMEN_TOLERANCIA_RED_S
        entregada = (
            datetime.fromisoformat(activa["entregada_en"])
            if activa and activa.get("entregada_en")
            else ahora
        )
        elapsed = (ahora - entregada).total_seconds() - activa.get("pausa_s", 0)
        restantes = max(0.0, limite - elapsed)

        return ReanudarRespuesta(
            pausado=False,
            decision=decision,
            segundos_restantes=restantes,
        )
