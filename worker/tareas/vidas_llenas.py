from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_config
from app.core.reloj import now
from app.modelos.apelaciones import Notificacion
from app.modelos.enums import EstadoCuenta
from app.modelos.usuarios import Usuario
from worker.candado import candado_redis
from worker.ventana import calcular_programada_para


async def tarea_vidas_llenas(sesion: AsyncSession) -> int:
    async with candado_redis("tarea:vidas_llenas", ttl_segundos=800) as adquirido:
        if not adquirido:
            return 0

        cfg = get_config()
        ahora = now()

        q = select(Usuario).where(
            Usuario.estado_cuenta == EstadoCuenta.activo,
            Usuario.vidas == 0,
        )
        res = await sesion.execute(q)
        usuarios = list(res.scalars())

        creadas = 0
        for u in usuarios:
            delta_s = (ahora - u.vidas_base_en).total_seconds()
            regeneradas = int(delta_s // cfg.VIDA_REGEN_SEGUNDOS)
            if regeneradas < cfg.VIDAS_MAX:
                continue

            prefs = u.preferencias if isinstance(u.preferencias, dict) else {}
            if not prefs.get("notif_vidas", True):
                continue

            q_existente = select(Notificacion).where(
                Notificacion.usuario_id == u.id,
                Notificacion.tipo == "vidas",
                Notificacion.programada_para >= u.vidas_base_en,
            )
            res_ex = await sesion.execute(q_existente)
            if res_ex.first() is not None:
                continue

            programada = calcular_programada_para(ahora, u.zona_horaria)
            notif = Notificacion(
                usuario_id=u.id,
                tipo="vidas",
                titulo="Vidas llenas",
                cuerpo="¡Tus vidas están al máximo! (5/5)",
                programada_para=programada,
                estado="pendiente",
            )
            sesion.add(notif)
            creadas += 1

        if creadas > 0:
            await sesion.commit()

        return creadas
