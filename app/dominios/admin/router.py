from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sesion
from app.core.deps import UsuarioAdmin
from app.dominios.admin.servicio import AdminServicio
from app.esquemas.admin import (
    ActualizarComodinInput,
    CargarEscenarioInput,
    ComodinAdminRespuesta,
    CrearTarjetaInput,
    EditarTarjetaInput,
    EstadoTarjetaInput,
    MetricasAdminRespuesta,
    ReemplazarEscenarioInput,
    TarjetaAdminRespuesta,
)

router = APIRouter()


def _admin_id(payload: dict) -> uuid.UUID:
    return uuid.UUID(payload["sub"])


@router.get("/tarjetas", response_model=list[TarjetaAdminRespuesta])
async def listar_tarjetas(
    payload: UsuarioAdmin,
    sprint_id: int | None = Query(default=None),
    tipo: str | None = Query(default=None),
    activa: bool | None = Query(default=None),
    version: int | None = Query(default=None),
    sesion: AsyncSession = Depends(get_sesion),
) -> list[TarjetaAdminRespuesta]:
    return await AdminServicio(sesion).listar_tarjetas(sprint_id, tipo, activa, version)


@router.post("/tarjetas", response_model=TarjetaAdminRespuesta, status_code=201)
async def crear_tarjeta(
    datos: CrearTarjetaInput,
    payload: UsuarioAdmin,
    sesion: AsyncSession = Depends(get_sesion),
) -> TarjetaAdminRespuesta:
    return await AdminServicio(sesion).crear_tarjeta(_admin_id(payload), datos)


@router.put("/tarjetas/{id}", response_model=TarjetaAdminRespuesta)
async def editar_tarjeta(
    id: uuid.UUID,
    datos: EditarTarjetaInput,
    payload: UsuarioAdmin,
    sesion: AsyncSession = Depends(get_sesion),
) -> TarjetaAdminRespuesta:
    return await AdminServicio(sesion).editar_tarjeta(_admin_id(payload), id, datos)


@router.patch("/tarjetas/{id}/estado", response_model=TarjetaAdminRespuesta)
async def cambiar_estado_tarjeta(
    id: uuid.UUID,
    datos: EstadoTarjetaInput,
    payload: UsuarioAdmin,
    sesion: AsyncSession = Depends(get_sesion),
) -> TarjetaAdminRespuesta:
    return await AdminServicio(sesion).cambiar_estado_tarjeta(_admin_id(payload), id, datos)


@router.post("/escenarios")
async def cargar_escenario(
    datos: CargarEscenarioInput,
    payload: UsuarioAdmin,
    sesion: AsyncSession = Depends(get_sesion),
) -> dict[str, str]:
    return await AdminServicio(sesion).cargar_escenario(_admin_id(payload), datos)


@router.put("/escenarios/{id}")
async def reemplazar_escenario(
    id: int,
    datos: ReemplazarEscenarioInput,
    payload: UsuarioAdmin,
    sesion: AsyncSession = Depends(get_sesion),
) -> dict[str, str]:
    return await AdminServicio(sesion).reemplazar_escenario(_admin_id(payload), id, datos)


@router.put("/comodines/{id}", response_model=ComodinAdminRespuesta)
async def actualizar_comodin(
    id: str,
    datos: ActualizarComodinInput,
    payload: UsuarioAdmin,
    sesion: AsyncSession = Depends(get_sesion),
) -> ComodinAdminRespuesta:
    return await AdminServicio(sesion).actualizar_comodin(_admin_id(payload), id, datos)


@router.get("/metricas", response_model=MetricasAdminRespuesta)
async def metricas_admin(
    payload: UsuarioAdmin,
    sesion: AsyncSession = Depends(get_sesion),
) -> MetricasAdminRespuesta:
    return await AdminServicio(sesion).metricas()
