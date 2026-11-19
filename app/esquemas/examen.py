from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.esquemas.juego import CierreIntentoRespuesta


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IniciarExamenInput(_Base):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)


class DecisionExamen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    orden: int
    hora_crisis: int
    tarjeta: dict[str, Any]
    segundos_limite: float


class ContraargumentoInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    replica_jefe: str
    fundamentos: list[dict[str, Any]]
    segundos_limite: float


class IniciarExamenRespuesta(BaseModel):
    intento_id: uuid.UUID
    hp_jefe: int
    vidas: int
    titulo_crisis: str
    descripcion_crisis: str
    decision: DecisionExamen


class ContraargumentoInput(_Base):
    respuesta_id: uuid.UUID
    fundamento_id: int


class ContraargumentoRespuesta(BaseModel):
    hp_jefe: int
    vidas: int
    contraargumento_ok: bool
    siguiente_decision: DecisionExamen | None
    cierre: CierreIntentoRespuesta | None


class PausaRespuesta(BaseModel):
    pausado: bool
    pausado_en: datetime
    pausa_acumulada_s: int


class ReanudarRespuesta(BaseModel):
    pausado: bool
    decision: DecisionExamen
    segundos_restantes: float
