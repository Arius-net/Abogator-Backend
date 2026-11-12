from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.esquemas.contenido import ContenidoInteractivo, EscenarioJefe


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModuloProgresoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: int
    titulo: str
    etapa_startup: str
    color_token: str
    activo: bool
    sprints_completados: int
    total_sprints: int
    examen_aprobado: bool


class SprintRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    modulo_id: int
    orden: int
    es_examen: bool
    titulo: str
    objetivo: str
    estado: str
    estrellas: int
    mejor_aciertos: int
    perfecto: bool


class SprintIntroRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    modulo_id: int
    orden: int
    es_examen: bool
    titulo: str
    objetivo: str
    ini_presupuesto: int
    ini_reputacion: int
    ini_velocidad: int
    ini_riesgo: int
    monedas_max: int


class CrearTarjetaInput(_Base):
    sprint_id: int
    tipo: str = Field(pattern="^(normal|evidencia|justificacion)$")
    categoria: str = Field(min_length=1, max_length=60)
    personaje_nombre: str = Field(min_length=1, max_length=60)
    personaje_rol: str = Field(min_length=1, max_length=60)
    iniciales: str = Field(min_length=1, max_length=3)
    texto: str = Field(min_length=1)
    explicacion: str = Field(min_length=1)
    nota_abogado: str | None = None
    array_palabras_trampa: list[str] | None = None
    contenido_interactivo: ContenidoInteractivo


class EditarTarjetaInput(_Base):
    sprint_id: int | None = None
    tipo: str | None = Field(default=None, pattern="^(normal|evidencia|justificacion)$")
    categoria: str | None = Field(default=None, max_length=60)
    personaje_nombre: str | None = Field(default=None, max_length=60)
    personaje_rol: str | None = Field(default=None, max_length=60)
    iniciales: str | None = Field(default=None, max_length=3)
    texto: str | None = None
    explicacion: str | None = None
    nota_abogado: str | None = None
    array_palabras_trampa: list[str] | None = None
    contenido_interactivo: ContenidoInteractivo | None = None


class EstadoTarjetaInput(_Base):
    activa: bool


class TarjetaAdminRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    sprint_id: int
    tipo: str
    categoria: str
    personaje_nombre: str
    personaje_rol: str
    iniciales: str
    texto: str
    explicacion: str
    nota_abogado: str | None
    array_palabras_trampa: list[str] | None
    contenido_interactivo: dict[str, Any]
    activa: bool
    actualizado_en: datetime


class CargarEscenarioInput(_Base):
    sprint_id: int
    escenario: EscenarioJefe


class ReemplazarEscenarioInput(_Base):
    escenario: EscenarioJefe


class ActualizarComodinInput(_Base):
    precio: int | None = Field(default=None, ge=1)
    activo: bool | None = None


class ComodinAdminRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clave: str
    nombre: str
    descripcion: str
    precio: int
    permitido_en_examen: bool
    activo: bool


class MetricasAdminRespuesta(BaseModel):
    tasa_acierto_tarjetas: list[dict[str, Any]]
    quiebras_por_sprint: list[dict[str, Any]]
    retencion_apelaciones: dict[str, Any]
