from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sesion
from app.core.deps import UsuarioActual
from app.dominios.sync.servicio import SyncServicio
from app.esquemas.sync import SyncRespuestasInput, SyncRespuestasRespuesta

router = APIRouter()


def _uid(payload: dict) -> uuid.UUID:
    return uuid.UUID(payload["sub"])


@router.post("/sync/respuestas", response_model=SyncRespuestasRespuesta)
async def sincronizar_respuestas(
    datos: SyncRespuestasInput,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> SyncRespuestasRespuesta:
    return await SyncServicio(sesion).sincronizar(_uid(payload), datos)
