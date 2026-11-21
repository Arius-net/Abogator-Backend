from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.esquemas.juego import CierreIntentoRespuesta


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ElementoSyncInput(_Base):
    intento_id: uuid.UUID
    id: uuid.UUID
    tarjeta_id: uuid.UUID
    veredicto: str
    segundos: float = Field(ge=0.0)
    por_que_opcion_id: int | None = None
    lineas_subrayadas: list[int] | None = None
    justificacion_opcion_id: int | None = None
    respondido_en: datetime | None = None


class SyncRespuestasInput(_Base):
    respuestas: list[ElementoSyncInput] = Field(max_length=50)


class ResultadoSync(BaseModel):
    id: uuid.UUID
    estado: str
    resultado: str | None = None
    motivo: str | None = None


class EstadoJugadorSync(BaseModel):
    vidas: int
    monedas: int
    xp: int
    nivel: int
    racha_actual: int
    amparo_activo: bool


class IntentoSyncResumen(BaseModel):
    id: uuid.UUID
    estado: str
    indicadores: dict[str, int]
    cierre: CierreIntentoRespuesta | None = None


class SyncRespuestasRespuesta(BaseModel):
    resultados: list[ResultadoSync]
    jugador: EstadoJugadorSync
    intentos: list[IntentoSyncResumen]
