from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos.apelaciones import Apelacion, JuicioApelacion
from app.modelos.contenido import Tarjeta
from app.modelos.economia import MovimientoEconomia
from app.modelos.enums import EstadoApelacion
from app.modelos.usuarios import Usuario


class ApelacionesRepositorio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def listar_apelaciones_pendientes(
        self, usuario_id: uuid.UUID
    ) -> list[Apelacion]:
        res = await self._s.execute(
            select(Apelacion)
            .where(
                Apelacion.usuario_id == usuario_id,
                Apelacion.estado == EstadoApelacion.pendiente,
            )
            .order_by(Apelacion.proxima_revision.asc())
        )
        return list(res.scalars())

    async def buscar_apelacion_por_id(
        self, apelacion_id: uuid.UUID
    ) -> Apelacion | None:
        return await self._s.get(Apelacion, apelacion_id)

    async def buscar_apelacion_con_lock(
        self, apelacion_id: uuid.UUID
    ) -> Apelacion | None:
        res = await self._s.execute(
            select(Apelacion)
            .where(Apelacion.id == apelacion_id)
            .with_for_update()
        )
        return res.scalar_one_or_none()

    async def buscar_usuario_con_lock(
        self, usuario_id: uuid.UUID
    ) -> Usuario | None:
        res = await self._s.execute(
            select(Usuario)
            .where(Usuario.id == usuario_id)
            .with_for_update()
        )
        return res.scalar_one_or_none()

    async def buscar_tarjeta_version(
        self, tarjeta_id: uuid.UUID, version: int
    ) -> Tarjeta | None:
        res = await self._s.execute(
            select(Tarjeta).where(
                Tarjeta.id == tarjeta_id,
                Tarjeta.version == version,
            )
        )
        return res.scalar_one_or_none()

    async def buscar_juicio_por_id(
        self, juicio_id: uuid.UUID
    ) -> JuicioApelacion | None:
        return await self._s.get(JuicioApelacion, juicio_id)

    async def crear_juicio(self, juicio: JuicioApelacion) -> None:
        self._s.add(juicio)

    async def crear_movimiento_economia(self, mov: MovimientoEconomia) -> None:
        self._s.add(mov)
