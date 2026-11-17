from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sesion
from app.core.deps import UsuarioActual
from app.dominios.tienda.servicio import TiendaServicio
from app.esquemas.tienda import ComodinTiendaRespuesta, CompraRespuesta, ComprarComodinInput

router = APIRouter()


def _uid(payload: dict) -> uuid.UUID:
    return uuid.UUID(payload["sub"])


@router.get("/tienda", response_model=list[ComodinTiendaRespuesta])
async def catalogo_tienda(
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> list[ComodinTiendaRespuesta]:
    return await TiendaServicio(sesion).listar_catalogo()


@router.post("/tienda/compras", response_model=CompraRespuesta)
async def comprar_comodin(
    datos: ComprarComodinInput,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> CompraRespuesta:
    return await TiendaServicio(sesion).comprar_comodin(_uid(payload), datos)
