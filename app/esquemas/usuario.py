from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.esquemas.jsonb import Inventario, Preferencias, RetoDiario



class UsuarioRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    correo: str
    perfil: str
    rol: str
    estado_cuenta: str
    zona_horaria: str
    nivel: int
    xp: int
    monedas: int
    racha_actual: int
    racha_maxima: int
    creado_en: datetime
    ultimo_acceso: datetime | None



class ActualizarCuentaInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    perfil: str | None = None
    zona_horaria: str | None = Field(default=None, max_length=60)

    from pydantic import field_validator

    @field_validator("perfil")
    @classmethod
    def validar_perfil(cls, v: str | None) -> str | None:
        if v is not None and v not in ("estudiante", "desarrollador", "legal"):
            raise ValueError("Perfil inválido.")
        return v



class EstadoRespuesta(BaseModel):
    vidas: int
    vidas_max: int
    proxima_vida_en: datetime | None   # null si vidas == vidas_max
    monedas: int
    xp: int
    nivel: int
    racha_actual: int
    amparo_activo: bool





class DispositivoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plataforma: str = Field(pattern="^(android|ios)$")
    token: str = Field(min_length=1)


class DispositivoRespuesta(BaseModel):
    id: uuid.UUID
    plataforma: str
    activo: bool



class DatosPersonalesRespuesta(BaseModel):
    id: uuid.UUID
    nombre: str
    correo: str
    perfil: str
    zona_horaria: str
    creado_en: datetime
    consentimientos: list[dict[str, Any]]
    dispositivos_push: list[dict[str, Any]]



class InventarioRespuesta(BaseModel):
    inventario: Inventario



class MovimientoRespuesta(BaseModel):
    id: int
    recurso: str
    cantidad: int
    saldo_resultante: int
    motivo: str
    detalle: dict[str, Any] | None
    creado_en: datetime


class MovimientosPaginados(BaseModel):
    items: list[MovimientoRespuesta]
    total: int
    pagina: int
    por_pagina: int



class ProgresoModuloRespuesta(BaseModel):
    modulo_id: int
    numero: int
    titulo: str
    sprints_completados: int
    total_sprints: int
    examen_aprobado: bool


class PerfilRespuesta(BaseModel):
    precision_global: float       # % de respuestas correctas
    racha_actual: int
    racha_maxima: int
    sprints_perfectos: int        # con 3 estrellas
    progreso_modulos: list[ProgresoModuloRespuesta]



class InsigniaRespuesta(BaseModel):
    clave: str
    nombre: str
    descripcion: str
    icono: str
    obtenida: bool
    obtenida_en: datetime | None



class CertificadoRespuesta(BaseModel):
    folio: str
    modulo_numero: int
    modulo_titulo: str
    emitido_en: datetime
    nombre_usuario: str



class RetoRespuesta(BaseModel):
    fecha_reto: date
    tipo: str
    descripcion: str
    meta: int
    avance: int
    completado: bool
    recompensa_monedas: int
