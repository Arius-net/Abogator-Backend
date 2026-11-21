from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_config
from app.core.reloj import now
from app.modelos.enums import EstadoIntento, TipoIntento
from app.modelos.juego import Intento
from worker.candado import candado_redis


async def tarea_pausas_examen_vencidas(sesion: AsyncSession) -> int:
    async with candado_redis("tarea:pausas_examen_vencidas", ttl_segundos=50) as adquirido:
        if not adquirido:
            return 0

        cfg = get_config()
        ahora = now()

        q = (
            select(Intento)
            .where(
                Intento.tipo == TipoIntento.examen,
                Intento.estado == EstadoIntento.en_curso,
                Intento.pausado_en != None,
            )
            .with_for_update()
        )
        res = await sesion.execute(q)
        examenes = list(res.scalars())

        cerrados = 0
        for it in examenes:
            dur = (ahora - it.pausado_en).total_seconds()
            if (it.pausa_acumulada_s or 0) + dur > cfg.EXAMEN_PAUSA_MAX_S:
                it.estado = EstadoIntento.abandonado
                it.terminado_en = ahora
                cerrados += 1

        if cerrados > 0:
            await sesion.commit()

        return cerrados
