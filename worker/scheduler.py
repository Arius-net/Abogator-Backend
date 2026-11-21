from __future__ import annotations

import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.db import _get_session_factory
from worker.tareas.anonimizacion import tarea_anonimizacion
from worker.tareas.apelaciones_vencidas import tarea_apelaciones_vencidas
from worker.tareas.cierre_racha import tarea_cierre_racha
from worker.tareas.envio_push import tarea_envio_push
from worker.tareas.intentos_abandonados import tarea_intentos_abandonados
from worker.tareas.pausas_examen_vencidas import tarea_pausas_examen_vencidas
from worker.tareas.recordatorio_racha import tarea_recordatorio_racha
from worker.tareas.vidas_llenas import tarea_vidas_llenas

logger = logging.getLogger(__name__)


async def _ejecutar_con_sesion(tarea_fn):
    factory = _get_session_factory()
    async with factory() as sesion:
        try:
            return await tarea_fn(sesion)
        except Exception as exc:
            logger.error(f"Error en tarea {tarea_fn.__name__}: {exc}")


def crear_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        lambda: _ejecutar_con_sesion(tarea_apelaciones_vencidas),
        "interval",
        minutes=5,
        id="tarea_apelaciones_vencidas",
        name="Apelaciones vencidas",
        replace_existing=True,
    )

    scheduler.add_job(
        lambda: _ejecutar_con_sesion(tarea_envio_push),
        "interval",
        minutes=1,
        id="tarea_envio_push",
        name="Envío de notificaciones push",
        replace_existing=True,
    )

    scheduler.add_job(
        lambda: _ejecutar_con_sesion(tarea_vidas_llenas),
        "interval",
        minutes=15,
        id="tarea_vidas_llenas",
        name="Notificación de vidas llenas",
        replace_existing=True,
    )

    scheduler.add_job(
        lambda: _ejecutar_con_sesion(tarea_cierre_racha),
        "interval",
        hours=1,
        id="tarea_cierre_racha",
        name="Cierre de racha diario",
        replace_existing=True,
    )

    scheduler.add_job(
        lambda: _ejecutar_con_sesion(tarea_recordatorio_racha),
        "interval",
        hours=1,
        id="tarea_recordatorio_racha",
        name="Recordatorio de racha 19:00",
        replace_existing=True,
    )

    scheduler.add_job(
        lambda: _ejecutar_con_sesion(tarea_intentos_abandonados),
        "interval",
        hours=1,
        id="tarea_intentos_abandonados",
        name="Cierre de intentos abandonados 24h",
        replace_existing=True,
    )

    scheduler.add_job(
        lambda: _ejecutar_con_sesion(tarea_pausas_examen_vencidas),
        "interval",
        minutes=1,
        id="tarea_pausas_examen_vencidas",
        name="Pausas de examen vencidas",
        replace_existing=True,
    )

    scheduler.add_job(
        lambda: _ejecutar_con_sesion(tarea_anonimizacion),
        "cron",
        hour=3,
        minute=0,
        id="tarea_anonimizacion",
        name="Anonimización de cuentas borradas",
        replace_existing=True,
    )

    return scheduler


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def main() -> None:
        scheduler = crear_scheduler()
        scheduler.start()
        logger.info("Worker iniciado. Esperando tareas...")
        try:
            while True:
                await asyncio.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()

    asyncio.run(main())
