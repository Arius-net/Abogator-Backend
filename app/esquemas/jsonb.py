from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field



class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")



class Preferencias(_Base):
    modo_oscuro: bool = False
    escala_texto: float = Field(default=1.0, ge=1.0, le=2.0)
    etiquetas_lector: bool = False
    botones_en_lugar_de_deslizar: bool = False
    haptica: bool = True
    tiempo_extendido: bool = False
    reducir_animaciones: bool = False
    notif_racha: bool = True
    notif_apelaciones: bool = True
    notif_vidas: bool = True

    @classmethod
    def por_defecto(cls) -> "Preferencias":
        return cls()



class Inventario(_Base):
    lupa: int = Field(default=0, ge=0)
    abogado: int = Field(default=0, ge=0)
    amparo: int = Field(default=0, ge=0)
    congelar_racha: int = Field(default=0, ge=0)

    @classmethod
    def vacio(cls) -> "Inventario":
        return cls()



TipoReto = Literal[
    "aciertos_seguidos",
    "sprints_completados",
    "por_que_correctos",
    "evidencias_inspeccionadas",
]

_PLANTILLAS: list[dict[str, Any]] = [
    {"tipo": "aciertos_seguidos",        "descripcion": "Acierta 3 tarjetas seguidas",   "meta": 3,  "recompensa_monedas": 15},
    {"tipo": "sprints_completados",       "descripcion": "Completa 1 sprint",             "meta": 1,  "recompensa_monedas": 15},
    {"tipo": "por_que_correctos",         "descripcion": 'Acierta 2 "¿Por qué?"',         "meta": 2,  "recompensa_monedas": 15},
    {"tipo": "evidencias_inspeccionadas", "descripcion": "Inspecciona 1 evidencia",        "meta": 1,  "recompensa_monedas": 15},
]


class RetoDiario(_Base):
    fecha_reto: date
    tipo: TipoReto
    descripcion: str
    meta: int = Field(ge=1)
    avance: int = Field(default=0, ge=0)
    completado: bool = False
    recompensa_monedas: int = Field(default=15, ge=0)

    @classmethod
    def de_hoy(cls, fecha_hoy: date) -> "RetoDiario":
        """Genera el reto del día según la plantilla (día del año % 4)."""
        dia = fecha_hoy.timetuple().tm_yday
        plantilla = _PLANTILLAS[dia % 4]
        return cls(
            fecha_reto=fecha_hoy,
            tipo=plantilla["tipo"],
            descripcion=plantilla["descripcion"],
            meta=plantilla["meta"],
            avance=0,
            completado=False,
            recompensa_monedas=plantilla["recompensa_monedas"],
        )



class DetalleMovimiento(_Base):
    model_config = ConfigDict(extra="forbid")

    intento_id: str | None = None
    tarjeta_id: str | None = None
    comodin: str | None = None
    cantidad_comprada: int | None = None
    precio_unitario: int | None = None
    bonos: list[str] | None = None
    estado_intento: str | None = None



class CambiosAuditoria(_Base):
    antes: Any = None
    despues: Any = None
