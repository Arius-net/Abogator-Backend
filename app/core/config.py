from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_RUTA_PROYECTO = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _RUTA_PROYECTO / ".env"


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ENV_FILE, ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+asyncpg://abogator:abogator@localhost:5432/abogator"
    REDIS_URL: str = "redis://localhost:6379/0"
    JWT_SECRET: str = "dev-secret-cambiar-en-produccion-jwt-32chars"
    PAQUETE_SECRET: str = "dev-secret-cambiar-en-produccion-paquete"

    API_BASE_URL: str = ""

    MULTIPLICADOR_PUNTAJE: int = Field(default=1, ge=1)
    XP_POR_NIVEL: int = Field(default=100, ge=1)
    VIDAS_MAX: int = Field(default=5, ge=1)
    VIDA_REGEN_SEGUNDOS: int = Field(default=7200, ge=1)  # 2 h

    EXAMEN_SEGUNDOS_DECISION: int = Field(default=15, ge=1)
    EXAMEN_SEGUNDOS_CONTRA: int = Field(default=8, ge=1)
    EXAMEN_TOLERANCIA_RED_S: int = Field(default=2, ge=0)
    EXAMEN_TIEMPO_EXTENDIDO: float = Field(default=1.5, ge=1.0)
    EXAMEN_PAUSA_MAX_S: int = Field(default=600, ge=0)  # 10 min total

    APELACION_DIAS: list[int] = Field(default=[3, 7, 14])

    SOSPECHA_MIN_ACIERTOS: int = Field(default=5, ge=1)
    SOSPECHA_SEGUNDOS: float = Field(default=2.0, ge=0.1)

    ACCESS_TOKEN_MIN: int = Field(default=15, ge=1)
    REFRESH_TOKEN_DIAS: int = Field(default=30, ge=1)

    LOGIN_MAX_INTENTOS: int = Field(default=10, ge=1)
    LOGIN_VENTANA_MIN: int = Field(default=15, ge=1)
    RATE_LIMIT_USUARIO_MIN: int = Field(default=120, ge=1)

    ANONIMIZAR_DESPUES_DIAS: int = Field(default=30, ge=1)

    VERSION_AVISO_PRIVACIDAD: str = "v0-prueba"
    VERSION_TERMINOS: str = "v0-prueba"

    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""

    PUSH_BACKEND: Literal["simulado", "real"] = "simulado"
    CORREO_BACKEND: Literal["mailpit", "ses"] = "mailpit"

    MAILPIT_HOST: str = "mailpit"
    MAILPIT_PORT: int = 1025
    CORREO_REMITENTE: str = "noreply@abogator.local"


@lru_cache
def get_config() -> Configuracion:
    """Instancia única de configuración (cacheada). Inyectable en pruebas."""
    return Configuracion()  # type: ignore[call-arg]
