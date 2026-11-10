from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_config
from app.core.db import get_sesion
from app.core.errores import DemasiasiasPeticiones
from app.core.rate_limit import verificar_rate_login
from app.core.redis_client import get_redis
from app.dominios.auth.servicio import AuthServicio
from app.esquemas.auth import (
    LoginInput,
    LogoutInput,
    MensajeRespuesta,
    RecuperarInput,
    RegistroInput,
    RenovarInput,
    RestablecerInput,
    TokensRespuesta,
)

router = APIRouter()


def _ip_cliente(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


@router.post(
    "/registro",
    response_model=TokensRespuesta,
    status_code=201,
    summary="Registra una nueva cuenta",
)
async def registro(
    datos: RegistroInput,
    request: Request,
    sesion: AsyncSession = Depends(get_sesion),
) -> TokensRespuesta:
    cfg = get_config()
    servicio = AuthServicio(sesion)
    access, refresh = await servicio.registrar(
        datos=datos,
        ip=_ip_cliente(request),
        version_aviso=cfg.VERSION_AVISO_PRIVACIDAD,
        version_terminos=cfg.VERSION_TERMINOS,
    )
    return TokensRespuesta(access_token=access, refresh_token=refresh)


@router.post(
    "/login",
    response_model=TokensRespuesta,
    summary="Inicia sesión",
)
async def login(
    datos: LoginInput,
    request: Request,
    sesion: AsyncSession = Depends(get_sesion),
) -> TokensRespuesta:
    ip = _ip_cliente(request)
    redis = get_redis()

    await verificar_rate_login(redis, ip, str(datos.correo))

    servicio = AuthServicio(sesion)
    access, refresh = await servicio.login(
        correo=str(datos.correo),
        contrasena=datos.contrasena,
        dispositivo=datos.dispositivo,
    )
    return TokensRespuesta(access_token=access, refresh_token=refresh)


@router.post(
    "/renovar",
    response_model=TokensRespuesta,
    summary="Rota el refresh token y emite un nuevo JWT",
)
async def renovar(
    datos: RenovarInput,
    sesion: AsyncSession = Depends(get_sesion),
) -> TokensRespuesta:
    servicio = AuthServicio(sesion)
    access, refresh = await servicio.renovar(datos.refresh_token)
    return TokensRespuesta(access_token=access, refresh_token=refresh)


@router.post(
    "/logout",
    response_model=MensajeRespuesta,
    summary="Cierra la sesión actual",
)
async def logout(
    datos: LogoutInput,
    sesion: AsyncSession = Depends(get_sesion),
) -> MensajeRespuesta:
    servicio = AuthServicio(sesion)
    await servicio.logout(datos.refresh_token)
    return MensajeRespuesta(mensaje="Sesión cerrada correctamente.")


@router.post(
    "/recuperar",
    response_model=MensajeRespuesta,
    summary="Envía el enlace de recuperación de contraseña",
)
async def recuperar(
    datos: RecuperarInput,
    sesion: AsyncSession = Depends(get_sesion),
) -> MensajeRespuesta:
    servicio = AuthServicio(sesion)
    await servicio.recuperar_contrasena(str(datos.correo))
    return MensajeRespuesta(
        mensaje="Si el correo existe, recibirás un enlace en los próximos minutos."
    )


@router.post(
    "/restablecer",
    response_model=MensajeRespuesta,
    summary="Cambia la contraseña con el token del enlace",
)
async def restablecer(
    datos: RestablecerInput,
    sesion: AsyncSession = Depends(get_sesion),
) -> MensajeRespuesta:
    servicio = AuthServicio(sesion)
    await servicio.restablecer_contrasena(datos.token, datos.nueva_contrasena)
    return MensajeRespuesta(mensaje="Contraseña actualizada correctamente.")
