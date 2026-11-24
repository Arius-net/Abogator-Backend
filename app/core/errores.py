from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class ErrorNegocio(Exception):
    """Excepción base para todos los errores de dominio de AboGator."""

    http_status: int = 400
    codigo: str = "ERROR"
    mensaje: str = "Ha ocurrido un error."

    def __init__(
        self,
        detalle: dict[str, Any] | None = None,
        mensaje: str | None = None,
    ) -> None:
        self.detalle = detalle
        if mensaje:
            self.mensaje = mensaje
        super().__init__(self.mensaje)


class NoAutenticado(ErrorNegocio):
    http_status = 401
    codigo = "NO_AUTENTICADO"
    mensaje = "Autenticación requerida."


class TokenExpirado(ErrorNegocio):
    http_status = 401
    codigo = "TOKEN_EXPIRADO"
    mensaje = "El token ha expirado."


class CredencialesInvalidas(ErrorNegocio):
    http_status = 401
    codigo = "CREDENCIALES_INVALIDAS"
    mensaje = "Correo o contraseña incorrectos."


class SinVidas(ErrorNegocio):
    http_status = 403
    codigo = "SIN_VIDAS"
    mensaje = "No tienes vidas disponibles."


class SprintBloqueado(ErrorNegocio):
    http_status = 403
    codigo = "SPRINT_BLOQUEADO"
    mensaje = "No puedes iniciar este sprint."


class SinPermiso(ErrorNegocio):
    http_status = 403
    codigo = "SIN_PERMISO"
    mensaje = "No tienes permiso para esta acción."


class PausaNoPermitida(ErrorNegocio):
    http_status = 403
    codigo = "PAUSA_NO_PERMITIDA"
    mensaje = "La pausa solo está disponible con tiempo extendido."


class NoEncontrado(ErrorNegocio):
    http_status = 404
    codigo = "NO_ENCONTRADO"
    mensaje = "Recurso no encontrado."


class IntentoEnCurso(ErrorNegocio):
    http_status = 409
    codigo = "INTENTO_EN_CURSO"
    mensaje = "Ya tienes un intento en curso."


class IntentoCerrado(ErrorNegocio):
    http_status = 409
    codigo = "INTENTO_CERRADO"
    mensaje = "El intento ya está cerrado."


class YaRespondida(ErrorNegocio):
    http_status = 409
    codigo = "YA_RESPONDIDA"
    mensaje = "Esta tarjeta ya fue respondida en el intento."


class EmailEnUso(ErrorNegocio):
    http_status = 409
    codigo = "EMAIL_EN_USO"
    mensaje = "Este correo ya está registrado."


class ComodinYaUsado(ErrorNegocio):
    http_status = 409
    codigo = "COMODIN_YA_USADO"
    mensaje = "Ya usaste este comodín en esta tarjeta o ya tienes uno activo."


class SaldoInsuficiente(ErrorNegocio):
    http_status = 409
    codigo = "SALDO_INSUFICIENTE"
    mensaje = "No tienes suficiente saldo para esta operación."


class PausaAgotada(ErrorNegocio):
    http_status = 409
    codigo = "PAUSA_AGOTADA"
    mensaje = "Has agotado el tiempo de pausa para este examen."


class PeticionInvalida(ErrorNegocio):
    http_status = 400
    codigo = "PETICION_INVALIDA"
    mensaje = "La petición no es válida."


class DemasiasiasPeticiones(ErrorNegocio):
    http_status = 429
    codigo = "DEMASIADAS_PETICIONES"
    mensaje = "Demasiadas peticiones. Intenta más tarde."


def _cuerpo_error(exc: ErrorNegocio, request_id: str) -> dict[str, Any]:
    return {
        "error": {
            "codigo": exc.codigo,
            "mensaje": exc.mensaje,
            "detalle": exc.detalle,
            "request_id": request_id,
        }
    }


async def handler_error_negocio(request: Request, exc: ErrorNegocio) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    headers: dict[str, str] = {}
    if isinstance(exc, DemasiasiasPeticiones) and exc.detalle:
        retry = exc.detalle.get("retry_after")
        if retry:
            headers["Retry-After"] = str(retry)
    return JSONResponse(
        status_code=exc.http_status,
        content=_cuerpo_error(exc, request_id),
        headers=headers,
    )
