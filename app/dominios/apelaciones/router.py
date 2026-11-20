from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sesion
from app.core.deps import UsuarioActual
from app.dominios.apelaciones.servicio import ApelacionesServicio
from app.esquemas.apelaciones import (
    BuzonApelacionesRespuesta,
    DetalleApelacionRespuesta,
    EnviarJuicioInput,
    JuicioRespuesta,
)

router = APIRouter()


def _uid(payload: dict) -> uuid.UUID:
    return uuid.UUID(payload["sub"])


@router.get("/apelaciones", response_model=BuzonApelacionesRespuesta)
async def obtener_buzon(
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> BuzonApelacionesRespuesta:
    return await ApelacionesServicio(sesion).obtener_buzon(_uid(payload))


@router.get("/apelaciones/{id}", response_model=DetalleApelacionRespuesta)
async def obtener_detalle(
    id: uuid.UUID,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> DetalleApelacionRespuesta:
    return await ApelacionesServicio(sesion).obtener_detalle(_uid(payload), id)


@router.post("/apelaciones/{id}/juicios", response_model=JuicioRespuesta)
async def resolver_juicio(
    id: uuid.UUID,
    datos: EnviarJuicioInput,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> JuicioRespuesta:
    return await ApelacionesServicio(sesion).resolver_juicio(_uid(payload), id, datos)
