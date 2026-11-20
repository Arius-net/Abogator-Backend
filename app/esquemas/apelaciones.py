from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApelacionResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tarjeta_id: uuid.UUID
    tarjeta_version: int
    etapa: int
    proxima_revision: datetime
    estado: str


class BuzonApelacionesRespuesta(BaseModel):
    vencidas: list[ApelacionResumen]
    proximas: list[ApelacionResumen]


class DetalleApelacionRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    etapa: int
    tarjeta_id: uuid.UUID
    tarjeta_version: int
    texto: str
    categoria: str
    personaje_nombre: str
    personaje_rol: str
    iniciales: str
    evidencia: dict[str, Any] | None


class EnviarJuicioInput(_Base):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    veredicto: str = Field(pattern="^(legal|ilegal|condicional|escalar)$")


class JuicioRespuesta(BaseModel):
    resultado: str
    vida_recuperada: bool
    etapa: int
    proxima_revision: datetime | None
    estado: str
    vidas: int
