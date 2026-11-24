from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

try:
    import email_validator  # noqa: F401
    from pydantic import EmailStr
except ImportError:
    EmailStr = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]  # type: ignore[misc]


def _validar_contrasena(v: str) -> str:
    """Mínimo 8 caracteres, al menos un número (06 §3)."""
    if len(v) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    if not any(c.isdigit() for c in v):
        raise ValueError("La contraseña debe contener al menos un número.")
    return v


class ConsentimientoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documento: str  # 'aviso_privacidad' | 'terminos'
    version: str

    @field_validator("documento")
    @classmethod
    def validar_documento(cls, v: str) -> str:
        if v not in ("aviso_privacidad", "terminos"):
            raise ValueError("Documento inválido. Use 'aviso_privacidad' o 'terminos'.")
        return v


class RegistroInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str = Field(min_length=1, max_length=80)
    correo: EmailStr
    contrasena: str
    perfil: str = "desarrollador"
    consentimientos: list[ConsentimientoInput] = Field(min_length=2, max_length=2)

    @field_validator("contrasena")
    @classmethod
    def validar_contrasena(cls, v: str) -> str:
        return _validar_contrasena(v)

    @field_validator("perfil")
    @classmethod
    def validar_perfil(cls, v: str) -> str:
        if v not in ("estudiante", "desarrollador", "legal"):
            raise ValueError("Perfil inválido.")
        return v


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    correo: EmailStr
    contrasena: str
    dispositivo: str | None = Field(default=None, max_length=80)


class RenovarInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str


class LogoutInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str


class RecuperarInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    correo: EmailStr


class RestablecerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str
    nueva_contrasena: str

    @field_validator("nueva_contrasena")
    @classmethod
    def validar_nueva(cls, v: str) -> str:
        return _validar_contrasena(v)


class TokensRespuesta(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MensajeRespuesta(BaseModel):
    mensaje: str
