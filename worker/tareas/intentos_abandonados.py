from __future__ import annotations

from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.reloj import now
from app.modelos.enums import EstadoIntento
from app.modelos.juego import Intento
from worker.candado import candado_redis


async def tarea_intentos_abandonados(sesion: AsyncSession) -> int:
    async with candado_redis("tarea:intentos_abandonados", ttl_segundos=3500) as adquirido:
        if not adquirido:
            return 0

        ahora = now()
        hace_24h = ahora - timedelta(hours=24)
        q = (
            select(Intento)
            .where(
                Intento.estado == EstadoIntento.en_curso,
                Intento.iniciado_en <= hace_24h,
            )
            .with_for_update()
        )
        res = await sesion.execute(q)
        intentos = list(res.scalars())

        for it in intentos:
            it.estado = EstadoIntento.abandonado
            it.terminado_en = ahora

        if intentos:
            await sesion.commit()

        return len(intentos)
