from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sesion
from app.core.deps import UsuarioActual
from app.dominios.usuarios.servicio import UsuariosServicio
from app.esquemas.jsonb import Preferencias
from app.esquemas.usuario import (
    ActualizarCuentaInput,
    CertificadoRespuesta,
    DatosPersonalesRespuesta,
    DispositivoInput,
    DispositivoRespuesta,
    EstadoRespuesta,
    InsigniaRespuesta,
    InventarioRespuesta,
    MovimientosPaginados,
    PerfilRespuesta,
    RetoRespuesta,
    UsuarioRespuesta,
)

router = APIRouter()


def _uid(payload: dict) -> uuid.UUID:
    """Extrae el UUID del 'sub' del JWT."""
    return uuid.UUID(payload["sub"])


@router.get(
    "/me",
    response_model=UsuarioRespuesta,
    summary="Perfil del usuario autenticado",
)
async def obtener_me(
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> UsuarioRespuesta:
    return await UsuariosServicio(sesion).obtener_usuario(_uid(payload))


@router.patch(
    "/me",
    response_model=UsuarioRespuesta,
    summary="Actualiza nombre, perfil o zona horaria",
)
async def actualizar_me(
    datos: ActualizarCuentaInput,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> UsuarioRespuesta:
    return await UsuariosServicio(sesion).actualizar_cuenta(_uid(payload), datos)


@router.get(
    "/me/estado",
    response_model=EstadoRespuesta,
    summary="Vidas (con regen lazy), monedas, XP y nivel actuales",
)
async def estado_me(
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> EstadoRespuesta:
    return await UsuariosServicio(sesion).estado_usuario(_uid(payload))


@router.put(
    "/me/preferencias",
    response_model=Preferencias,
    summary="Guarda las preferencias del usuario",
)
async def guardar_preferencias(
    prefs: Preferencias,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> Preferencias:
    return await UsuariosServicio(sesion).guardar_preferencias(_uid(payload), prefs)


@router.post(
    "/me/dispositivos",
    response_model=DispositivoRespuesta,
    status_code=201,
    summary="Registra o reactiva un token de notificación push",
)
async def registrar_dispositivo(
    datos: DispositivoInput,
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> DispositivoRespuesta:
    return await UsuariosServicio(sesion).registrar_dispositivo(
        _uid(payload), datos.plataforma, datos.token
    )


@router.get(
    "/me/datos",
    response_model=DatosPersonalesRespuesta,
    summary="Exporta todos los datos personales (ARCO)",
)
async def exportar_datos(
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> DatosPersonalesRespuesta:
    return await UsuariosServicio(sesion).exportar_datos(_uid(payload))


@router.delete(
    "/me",
    status_code=204,
    summary="Solicita el borrado de la cuenta (soft-delete)",
)
async def borrar_me(
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> Response:
    await UsuariosServicio(sesion).solicitar_borrado(_uid(payload))
    return Response(status_code=204)


@router.get(
    "/me/inventario",
    response_model=InventarioRespuesta,
    summary="Inventario de comodines del usuario",
)
async def inventario_me(
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> InventarioRespuesta:
    return await UsuariosServicio(sesion).inventario_usuario(_uid(payload))


@router.get(
    "/me/movimientos",
    response_model=MovimientosPaginados,
    summary="Historial de movimientos de economía (paginado)",
)
async def movimientos_me(
    payload: UsuarioActual,
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=20, ge=1, le=100),
    sesion: AsyncSession = Depends(get_sesion),
) -> MovimientosPaginados:
    return await UsuariosServicio(sesion).listar_movimientos(_uid(payload), pagina, por_pagina)


@router.get(
    "/me/perfil",
    response_model=PerfilRespuesta,
    summary="Estadísticas de rendimiento del jugador",
)
async def perfil_me(
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> PerfilRespuesta:
    return await UsuariosServicio(sesion).perfil_estadisticas(_uid(payload))


@router.get(
    "/me/insignias",
    response_model=list[InsigniaRespuesta],
    summary="Lista todas las insignias con estado obtenida/pendiente",
)
async def insignias_me(
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> list[InsigniaRespuesta]:
    return await UsuariosServicio(sesion).listar_insignias(_uid(payload))


@router.get(
    "/me/certificados",
    response_model=list[CertificadoRespuesta],
    summary="Lista los certificados emitidos al usuario",
)
async def certificados_me(
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> list[CertificadoRespuesta]:
    return await UsuariosServicio(sesion).listar_certificados(_uid(payload))


@router.get(
    "/retos/hoy",
    response_model=RetoRespuesta,
    summary="Reto diario del usuario (asignación lazy)",
)
async def reto_hoy(
    payload: UsuarioActual,
    sesion: AsyncSession = Depends(get_sesion),
) -> RetoRespuesta:
    return await UsuariosServicio(sesion).reto_hoy(_uid(payload))
