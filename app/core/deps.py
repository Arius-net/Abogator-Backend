from __future__ import annotations

import uuid
from typing import Annotated

import jwt as pyjwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errores import (
    NoAutenticado,
    SinPermiso,
    TokenExpirado,
)
from app.core.rate_limit import verificar_rate_usuario
from app.core.redis_client import get_redis
from app.core.security import decodificar_access_token
from app.modelos.enums import EstadoCuenta, RolUsuario

_bearer = HTTPBearer(auto_error=False)


async def _obtener_payload_jwt(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    if creds is None:
        raise NoAutenticado()
    try:
        payload = decodificar_access_token(creds.credentials)
    except pyjwt.ExpiredSignatureError:
        raise TokenExpirado()
    except pyjwt.InvalidTokenError:
        raise NoAutenticado()
    return payload


async def usuario_actual(
    request: Request,
    payload: Annotated[dict, Depends(_obtener_payload_jwt)],
) -> dict:
    """
    Dependencia que valida el JWT y aplica rate limiting por usuario.
    Devuelve el payload del token: {"sub": str(uuid), "rol": str, "perfil": str}.
    """
    usuario_id: str = payload.get("sub", "")
    if not usuario_id:
        raise NoAutenticado()

    redis = get_redis()
    await verificar_rate_usuario(redis, usuario_id)

    return payload


async def usuario_admin(
    payload: Annotated[dict, Depends(usuario_actual)],
) -> dict:
    """Exige que el usuario tenga rol 'admin'."""
    if payload.get("rol") != RolUsuario.admin.value:
        raise SinPermiso()
    return payload


UsuarioActual = Annotated[dict, Depends(usuario_actual)]
UsuarioAdmin = Annotated[dict, Depends(usuario_admin)]
