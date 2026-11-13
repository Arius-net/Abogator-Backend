from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sesion
from app.core.deps import UsuarioActual
from app.dominios.contenido.servicio import ContenidoServicio
from app.esquemas.admin import (
    ModuloProgresoRespuesta,
    SprintIntroRespuesta,
    SprintRespuesta,
)

router = APIRouter()


def _uid(payload: dict) -> uuid.UUID:
    return uuid.UUID(payload["sub"])


@router.get("/modulos", response_model=list[ModuloProgresoRespuesta])
async def listar_modulos(
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> list[ModuloProgresoRespuesta]:
    return await ContenidoServicio(sesion).listar_modulos_con_progreso(_uid(payload))


@router.get("/modulos/{id}/sprints", response_model=list[SprintRespuesta])
async def listar_sprints(
    id: int,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> list[SprintRespuesta]:
    return await ContenidoServicio(sesion).listar_sprints_de_modulo(_uid(payload), id)


@router.get("/sprints/{id}", response_model=SprintIntroRespuesta)
async def detalle_sprint(
    id: int,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> SprintIntroRespuesta:
    return await ContenidoServicio(sesion).detalle_sprint(id)
