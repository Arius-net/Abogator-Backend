from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IniciarSprintInput(_Base):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)


class PaqueteTarjeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    orden: int
    tarjeta_id: uuid.UUID
    version: int
    tipo: str
    categoria: str
    personaje_nombre: str
    personaje_rol: str
    iniciales: str
    texto: str
    evidencia: dict[str, Any] | None
    micro_pregunta: dict[str, Any]
    resolucion_cifrada: str


class PaqueteSprintRespuesta(BaseModel):
    intento_id: uuid.UUID
    clave_intento: str
    vidas: int
    indicadores: dict[str, int]
    tarjetas: list[PaqueteTarjeta]


class EnviarRespuestaInput(_Base):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tarjeta_id: uuid.UUID
    veredicto: str | None = None
    segundos: float = Field(ge=0.0)
    por_que_opcion_id: int | None = None
    lineas_subrayadas: list[int] | None = None
    justificacion_opcion_id: int | None = None
    respondido_en: datetime | None = None


class RecompensaRespuesta(BaseModel):
    xp: int
    monedas: int
    bonos: list[str]


class CierreIntentoRespuesta(BaseModel):
    estado: str
    estrellas: int
    xp_acreditada: int
    monedas_acreditadas: int
    indicadores: dict[str, int]
    insignias_nuevas: list[str]


class RespuestaEnvioRespuesta(BaseModel):
    resultado: str
    veredicto_correcto: str
    explicacion: str
    impacto: dict[str, int]
    indicadores: dict[str, int]
    recompensa: RecompensaRespuesta
    vidas: int
    amparo_usado: bool
    estado_intento: str
    siguiente_orden: int | None
    cierre: CierreIntentoRespuesta | None


class EstadoIntentoRespuesta(BaseModel):
    id: uuid.UUID
    sprint_id: int
    tipo: str
    estado: str
    vidas: int
    indicadores: dict[str, int]
    respuestas_completadas: int
    total_tarjetas: int
    xp_ganada: int
    monedas_ganadas: int
    clave_intento: str


class AbandonarRespuesta(BaseModel):
    id: uuid.UUID
    estado: str
    mensaje: str


class UsarComodinInput(_Base):
    comodin: str = Field(pattern="^(lupa|abogado|amparo)$")
    tarjeta_orden: int | None = Field(default=None, ge=1, le=10)


class UsarComodinRespuesta(BaseModel):
    comodin: str
    efecto: dict[str, Any]
    inventario: dict[str, int]
    amparo_activo: bool
