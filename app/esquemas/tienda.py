from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from app.esquemas.jsonb import Inventario


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ComodinTiendaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clave: str
    nombre: str
    descripcion: str
    precio: int
    permitido_en_examen: bool


class ComprarComodinInput(_Base):
    comodin: str = Field(pattern="^(lupa|abogado|amparo|congelar_racha)$")
    cantidad: int = Field(ge=1, le=10)


class CompraRespuesta(BaseModel):
    monedas: int
    inventario: Inventario
