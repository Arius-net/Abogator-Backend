from __future__ import annotations

from datetime import timedelta
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_config
from app.core.reloj import now
from app.modelos.enums import EstadoCuenta
from app.modelos.usuarios import DispositivoPush, SesionRefresh, Usuario
from worker.candado import candado_redis


async def tarea_anonimizacion(sesion: AsyncSession) -> int:
    async with candado_redis("tarea:anonimizacion", ttl_segundos=86000) as adquirido:
        if not adquirido:
            return 0

        cfg = get_config()
        ahora = now()
        hace_30dias = ahora - timedelta(days=cfg.ANONIMIZAR_DESPUES_DIAS)

        q = (
            select(Usuario)
            .where(
                Usuario.estado_cuenta == EstadoCuenta.pendiente_borrado,
                Usuario.eliminado_en <= hace_30dias,
            )
            .with_for_update()
        )
        res = await sesion.execute(q)
        usuarios = list(res.scalars())

        for u in usuarios:
            u.nombre = "Usuario Eliminado"
            u.correo = f"eliminado+{u.id}@anon.invalid"
            u.hash_contrasena = "*"

            await sesion.execute(
                delete(DispositivoPush).where(DispositivoPush.usuario_id == u.id)
            )
            await sesion.execute(
                delete(SesionRefresh).where(SesionRefresh.usuario_id == u.id)
            )

        if usuarios:
            await sesion.commit()

        return len(usuarios)
