from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.reloj import now
from app.esquemas.jsonb import Inventario
from app.modelos.enums import EstadoCuenta
from app.modelos.usuarios import Usuario
from worker.candado import candado_redis


async def tarea_cierre_racha(sesion: AsyncSession) -> int:
    async with candado_redis("tarea:cierre_racha", ttl_segundos=3500) as adquirido:
        if not adquirido:
            return 0

        ahora = now()
        q = select(Usuario).where(
            Usuario.estado_cuenta == EstadoCuenta.activo,
            Usuario.racha_actual > 0,
            Usuario.ultimo_dia_racha != None,
        ).with_for_update()
        res = await sesion.execute(q)
        usuarios = list(res.scalars())

        afectados = 0
        for u in usuarios:
            tz_str = u.zona_horaria or "America/Mexico_City"
            try:
                tz = ZoneInfo(tz_str)
            except Exception:
                tz = ZoneInfo("UTC")

            hoy_local = ahora.astimezone(tz).date()
            if u.ultimo_dia_racha is None or u.ultimo_dia_racha >= hoy_local - timedelta(days=1):
                continue

            inv = Inventario.model_validate(u.inventario)
            if inv.congelar_racha > 0:
                inv.congelar_racha -= 1
                u.inventario = inv.model_dump()
                u.ultimo_dia_racha = hoy_local - timedelta(days=1)
            else:
                u.racha_actual = 0

            afectados += 1

        if afectados > 0:
            await sesion.commit()

        return afectados
