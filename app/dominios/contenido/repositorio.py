from __future__ import annotations

import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modelos.contenido import Modulo, Sprint
from app.modelos.juego import ProgresoSprint


class ContenidoRepositorio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def listar_modulos(self) -> list[Modulo]:
        res = await self._s.execute(
            select(Modulo).where(Modulo.activo == True).order_by(Modulo.numero)
        )
        return list(res.scalars())

    async def buscar_modulo_por_id(self, modulo_id: int) -> Modulo | None:
        return await self._s.get(Modulo, modulo_id)

    async def listar_sprints_de_modulo(self, modulo_id: int) -> list[Sprint]:
        res = await self._s.execute(
            select(Sprint).where(Sprint.modulo_id == modulo_id).order_by(Sprint.orden)
        )
        return list(res.scalars())

    async def buscar_sprint_por_id(self, sprint_id: int) -> Sprint | None:
        return await self._s.get(Sprint, sprint_id)

    async def listar_progresos_usuario_modulo(
        self, usuario_id: uuid.UUID, modulo_id: int
    ) -> list[ProgresoSprint]:
        res = await self._s.execute(
            select(ProgresoSprint)
            .join(Sprint, ProgresoSprint.sprint_id == Sprint.id)
            .where(
                ProgresoSprint.usuario_id == usuario_id,
                Sprint.modulo_id == modulo_id,
            )
        )
        return list(res.scalars())

    async def listar_todos_progresos_usuario(self, usuario_id: uuid.UUID) -> list[ProgresoSprint]:
        res = await self._s.execute(
            select(ProgresoSprint).where(ProgresoSprint.usuario_id == usuario_id)
        )
        return list(res.scalars())
