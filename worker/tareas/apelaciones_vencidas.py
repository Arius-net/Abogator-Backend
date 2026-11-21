from __future__ import annotations

from datetime import timedelta
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.reloj import now
from app.modelos.apelaciones import Apelacion, Notificacion
from app.modelos.enums import EstadoApelacion
from app.modelos.usuarios import Usuario
from worker.candado import candado_redis
from worker.ventana import calcular_programada_para


async def tarea_apelaciones_vencidas(sesion: AsyncSession) -> int:
    async with candado_redis("tarea:apelaciones_vencidas", ttl_segundos=240) as adquirido:
        if not adquirido:
            return 0

        ahora = now()
        subq = (
            select(
                Apelacion.usuario_id,
                func.count(Apelacion.id).label("total"),
            )
            .where(
                Apelacion.estado == EstadoApelacion.pendiente,
                Apelacion.proxima_revision <= ahora,
            )
            .group_by(Apelacion.usuario_id)
        )
        res = await sesion.execute(subq)
        pendientes = res.all()

        creadas = 0
        hace_24h = ahora - timedelta(hours=24)

        for usuario_id, total in pendientes:
            u = await sesion.get(Usuario, usuario_id)
            if u is None:
                continue

            prefs = u.preferencias if isinstance(u.preferencias, dict) else {}
            if not prefs.get("notif_apelaciones", True):
                continue

            q_existente = select(Notificacion).where(
                Notificacion.usuario_id == usuario_id,
                Notificacion.tipo == "apelacion",
                (
                    (Notificacion.programada_para >= hace_24h)
                    | (Notificacion.enviada_en >= hace_24h)
                    | (Notificacion.estado == "pendiente")
                ),
            )
            res_ex = await sesion.execute(q_existente)
            if res_ex.first() is not None:
                continue

            cuerpo = (
                "Tienes 1 juicio de apelación pendiente"
                if total == 1
                else f"Tienes {total} juicios de apelación pendientes"
            )
            programada = calcular_programada_para(ahora, u.zona_horaria)

            notif = Notificacion(
                usuario_id=usuario_id,
                tipo="apelacion",
                titulo="Juicios de apelación pendientes",
                cuerpo=cuerpo,
                programada_para=programada,
                estado="pendiente",
            )
            sesion.add(notif)
            creadas += 1

        if creadas > 0:
            await sesion.commit()

        return creadas
