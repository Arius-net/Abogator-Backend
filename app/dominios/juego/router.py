from __future__ import annotations

import uuid
from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sesion
from app.core.deps import UsuarioActual
from app.dominios.juego.servicio import JuegoServicio
from app.esquemas.examen import (
    ContraargumentoInput,
    ContraargumentoRespuesta,
    IniciarExamenInput,
    IniciarExamenRespuesta,
    PausaRespuesta,
    ReanudarRespuesta,
)
from app.esquemas.juego import (
    AbandonarRespuesta,
    EnviarRespuestaInput,
    EstadoIntentoRespuesta,
    IniciarSprintInput,
    PaqueteSprintRespuesta,
    RespuestaEnvioRespuesta,
    UsarComodinInput,
    UsarComodinRespuesta,
)

router = APIRouter()


def _uid(payload: dict) -> uuid.UUID:
    return uuid.UUID(payload["sub"])


@router.post("/sprints/{id}/intentos", response_model=PaqueteSprintRespuesta, status_code=201)
async def iniciar_sprint(
    id: int,
    payload: UsuarioActual,
    datos: IniciarSprintInput = Body(default_factory=IniciarSprintInput),
    sesion: AsyncSession = Depends(get_sesion),
) -> PaqueteSprintRespuesta:
    return await JuegoServicio(sesion).iniciar_sprint(_uid(payload), id, datos)


@router.post("/intentos/{id}/respuestas", response_model=RespuestaEnvioRespuesta)
async def enviar_respuesta(
    id: uuid.UUID,
    datos: EnviarRespuestaInput,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> RespuestaEnvioRespuesta:
    return await JuegoServicio(sesion).enviar_respuesta(_uid(payload), id, datos)


@router.get("/intentos/{id}", response_model=EstadoIntentoRespuesta)
async def obtener_intento(
    id: uuid.UUID,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> EstadoIntentoRespuesta:
    return await JuegoServicio(sesion).obtener_intento(_uid(payload), id)


@router.post("/intentos/{id}/abandonar", response_model=AbandonarRespuesta)
async def abandonar_intento(
    id: uuid.UUID,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> AbandonarRespuesta:
    return await JuegoServicio(sesion).abandonar_intento(_uid(payload), id)


@router.post("/intentos/{id}/comodines", response_model=UsarComodinRespuesta)
async def usar_comodin(
    id: uuid.UUID,
    datos: UsarComodinInput,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> UsarComodinRespuesta:
    return await JuegoServicio(sesion).usar_comodin(_uid(payload), id, datos)


@router.post("/examenes/{sprint_id}/intentos", response_model=IniciarExamenRespuesta, status_code=201)
async def iniciar_examen(
    sprint_id: int,
    payload: UsuarioActual,
    datos: IniciarExamenInput = Body(default_factory=IniciarExamenInput),
    sesion: AsyncSession = Depends(get_sesion),
) -> IniciarExamenRespuesta:
    return await JuegoServicio(sesion).iniciar_examen(_uid(payload), sprint_id, datos)


@router.post("/intentos/{id}/contraargumento", response_model=ContraargumentoRespuesta)
async def responder_contraargumento(
    id: uuid.UUID,
    datos: ContraargumentoInput,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> ContraargumentoRespuesta:
    return await JuegoServicio(sesion).responder_contraargumento(_uid(payload), id, datos)


@router.post("/intentos/{id}/pausa", response_model=PausaRespuesta)
async def pausar_examen(
    id: uuid.UUID,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> PausaRespuesta:
    return await JuegoServicio(sesion).pausar_examen(_uid(payload), id)


@router.post("/intentos/{id}/reanudar", response_model=ReanudarRespuesta)
async def reanudar_examen(
    id: uuid.UUID,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> ReanudarRespuesta:
    return await JuegoServicio(sesion).reanudar_examen(_uid(payload), id)
