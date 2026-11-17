from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos.economia import Comodin, MovimientoEconomia
from app.modelos.usuarios import Usuario


class TiendaRepositorio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def listar_comodines_activos(self) -> list[Comodin]:
        res = await self._s.execute(
            select(Comodin).where(Comodin.activo == True).order_by(Comodin.precio)
        )
        return list(res.scalars())

    async def buscar_comodin_por_clave(self, clave: str) -> Comodin | None:
        res = await self._s.execute(
            select(Comodin).where(Comodin.clave == clave)
        )
        return res.scalar_one_or_none()

    async def buscar_usuario_con_lock(self, usuario_id: uuid.UUID) -> Usuario | None:
        res = await self._s.execute(
            select(Usuario).where(Usuario.id == usuario_id).with_for_update()
        )
        return res.scalar_one_or_none()

    async def crear_movimiento_economia(self, mov: MovimientoEconomia) -> None:
        self._s.add(mov)
