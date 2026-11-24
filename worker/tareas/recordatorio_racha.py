from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.reloj import now
from app.modelos.apelaciones import Notificacion
from app.modelos.enums import EstadoCuenta
from app.modelos.usuarios import Usuario
from worker.candado import candado_redis


async def tarea_recordatorio_racha(sesion: AsyncSession) -> int:
    async with candado_redis("tarea:recordatorio_racha", ttl_segundos=3500) as adquirido:
        if not adquirido:
            return 0

        ahora = now()
        q = select(Usuario).where(
            Usuario.estado_cuenta == EstadoCuenta.activo,
            Usuario.racha_actual > 0,
        )
        res = await sesion.execute(q)
        usuarios = list(res.scalars())

        creadas = 0
        for u in usuarios:
            tz_str = u.zona_horaria or "America/Mexico_City"
            try:
                tz = ZoneInfo(tz_str)
            except Exception:
                tz = ZoneInfo("UTC")

            ahora_local = ahora.astimezone(tz)
            if ahora_local.hour != 19:
                continue

            hoy_local = ahora_local.date()
            if u.ultimo_dia_racha == hoy_local:
                continue

            prefs = u.preferencias if isinstance(u.preferencias, dict) else {}
            if not prefs.get("notif_racha", True):
                continue

            inicio_dia_local = datetime.combine(hoy_local, time.min, tzinfo=tz).astimezone(
                timezone.utc
            )
            q_existente = select(Notificacion).where(
                Notificacion.usuario_id == u.id,
                Notificacion.tipo == "racha",
                Notificacion.programada_para >= inicio_dia_local,
            )
            res_ex = await sesion.execute(q_existente)
            if res_ex.first() is not None:
                continue

            notif = Notificacion(
                usuario_id=u.id,
                tipo="racha",
                titulo="¡Mantén tu racha!",
                cuerpo=f"No pierdas tu racha de {u.racha_actual} días",
                programada_para=ahora,
                estado="pendiente",
            )
            sesion.add(notif)
            creadas += 1

        if creadas > 0:
            await sesion.commit()

        return creadas
