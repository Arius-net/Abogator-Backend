from __future__ import annotations

import uuid
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VeredictoInfo(_Base):
    resultado: Literal["correcto", "parcial", "incorrecto"]
    d_presupuesto: int = Field(ge=-100, le=100)
    d_reputacion: int = Field(ge=-100, le=100)
    d_velocidad: int = Field(ge=-100, le=100)
    d_riesgo: int = Field(ge=-100, le=100)


class VeredictosDict(_Base):
    legal: VeredictoInfo
    ilegal: VeredictoInfo
    condicional: VeredictoInfo
    escalar: VeredictoInfo

    @model_validator(mode="after")
    def validar_resultados(self) -> VeredictosDict:
        todos = [self.legal, self.ilegal, self.condicional, self.escalar]
        correctos = sum(1 for v in todos if v.resultado == "correcto")
        parciales = sum(1 for v in todos if v.resultado == "parcial")

        if correctos != 1:
            raise ValueError("Debe haber exactamente un veredicto 'correcto'.")
        if parciales > 2:
            raise ValueError("No puede haber más de dos veredictos 'parcial'.")
        return self


class EvidenciaContenido(_Base):
    requerida: bool
    formato: Literal["codigo", "clausula"]
    nombre_archivo: str = Field(min_length=1)
    contenido_texto: str = Field(min_length=1)
    lineas_infractoras: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def validar_lineas(self) -> EvidenciaContenido:
        total_lineas = len(self.contenido_texto.splitlines())
        for linea in self.lineas_infractoras:
            if linea < 1 or linea > total_lineas:
                raise ValueError(
                    f"La línea infractora {linea} no existe en el contenido (total: {total_lineas})."
                )
        return self


class OpcionMicroPregunta(_Base):
    id: int
    texto: str = Field(min_length=1)
    es_correcta: bool


class MicroPregunta(_Base):
    tipo: Literal["por_que", "justificacion"]
    enunciado: str = Field(min_length=1)
    opciones: list[OpcionMicroPregunta] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validar_opciones(self) -> MicroPregunta:
        if len(self.opciones) != 2:
            raise ValueError("La micro pregunta debe tener exactamente 2 opciones.")
        ids = {o.id for o in self.opciones}
        if len(ids) != 2:
            raise ValueError("Los IDs de las opciones deben ser únicos.")
        correctas = sum(1 for o in self.opciones if o.es_correcta)
        if correctas != 1:
            raise ValueError("Exactamente una opción debe ser marcada como correcta.")
        return self


class ContenidoInteractivo(_Base):
    veredictos: VeredictosDict
    evidencia: EvidenciaContenido | None = None
    micro_pregunta: MicroPregunta

    def validar_para_tipo_tarjeta(self, tipo: str) -> None:
        if tipo == "normal":
            if self.evidencia is not None:
                raise ValueError("Las tarjetas de tipo normal no deben incluir evidencia.")
            if self.micro_pregunta.tipo != "por_que":
                raise ValueError("Las tarjetas de tipo normal deben tener micro pregunta 'por_que'.")
        elif tipo == "evidencia":
            if self.evidencia is None or not self.evidencia.requerida:
                raise ValueError("Las tarjetas de tipo evidencia requieren el bloque evidencia.")
            if self.micro_pregunta.tipo != "por_que":
                raise ValueError("Las tarjetas de tipo evidencia deben tener micro pregunta 'por_que'.")
        elif tipo == "justificacion":
            if self.evidencia is not None:
                raise ValueError("Las tarjetas de tipo justificacion no deben incluir evidencia.")
            if self.micro_pregunta.tipo != "justificacion":
                raise ValueError("Las tarjetas de tipo justificacion deben tener micro pregunta 'justificacion'.")
        else:
            raise ValueError(f"Tipo de tarjeta desconocido: {tipo}")


class DecisionFundamento(_Base):
    id: int
    texto: str = Field(min_length=1)
    es_correcta: bool


class DecisionJefe(_Base):
    orden: int = Field(ge=1, le=10)
    tarjeta_id: uuid.UUID
    hora_crisis: int
    replica_jefe: str = Field(min_length=1)
    fundamentos: list[DecisionFundamento] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validar_decision(self) -> DecisionJefe:
        if self.hora_crisis not in (0, 6, 24, 72):
            raise ValueError("hora_crisis debe ser 0, 6, 24 o 72.")
        ids = {f.id for f in self.fundamentos}
        if len(ids) != 2:
            raise ValueError("Los IDs de los fundamentos deben ser únicos.")
        correctas = sum(1 for f in self.fundamentos if f.es_correcta)
        if correctas != 1:
            raise ValueError("Exactamente un fundamento debe ser marcado como correcto.")
        return self


class EscenarioJefe(_Base):
    nombre_jefe: str = Field(min_length=1)
    titulo_crisis: str = Field(min_length=1)
    descripcion: str = Field(min_length=1)
    hp_inicial: int = Field(gt=0)
    dano_por_golpe: int = Field(gt=0)
    segundos_decision: int = Field(gt=0)
    segundos_contraargumento: int = Field(gt=0)
    decisiones: list[DecisionJefe] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def validar_decisiones(self) -> EscenarioJefe:
        ordeness = [d.orden for d in self.decisiones]
        if ordeness != list(range(1, 11)):
            raise ValueError("Las decisiones deben estar ordenadas del 1 al 10 consecutivamente.")
        for i in range(len(self.decisiones) - 1):
            if self.decisiones[i].hora_crisis > self.decisiones[i + 1].hora_crisis:
                raise ValueError("hora_crisis no puede decrecer entre decisiones consecutivas.")
        return self
