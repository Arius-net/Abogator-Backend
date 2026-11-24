from __future__ import annotations

import uuid
from typing import Any, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy import DateTime, Enum as SAEnum

from app.modelos.base import Base
from app.modelos.enums import TipoTarjeta

if TYPE_CHECKING:
    from app.modelos.juego import Intento, ProgresoSprint, Respuesta
    from app.modelos.apelaciones import Apelacion
    from app.modelos.logros import Certificado


class Modulo(Base):
    __tablename__ = "modulos"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    numero: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    titulo: Mapped[str] = mapped_column(String(80), nullable=False)
    etapa_startup: Mapped[str] = mapped_column(String(80), nullable=False)
    color_token: Mapped[str] = mapped_column(String(40), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    sprints: Mapped[list["Sprint"]] = relationship("Sprint", back_populates="modulo", lazy="raise")
    certificados: Mapped[list["Certificado"]] = relationship(
        "Certificado", back_populates="modulo", lazy="raise"
    )

    __table_args__ = (UniqueConstraint("numero", name="uq_modulos_numero"),)


class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    modulo_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("modulos.id"), nullable=False)
    orden: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    es_examen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    titulo: Mapped[str] = mapped_column(String(120), nullable=False)
    objetivo: Mapped[str] = mapped_column(Text, nullable=False)

    ini_presupuesto: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ini_reputacion: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ini_velocidad: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ini_riesgo: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    monedas_max: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=60)

    escenario_jefe: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    modulo: Mapped["Modulo"] = relationship("Modulo", back_populates="sprints", lazy="raise")
    tarjetas: Mapped[list["Tarjeta"]] = relationship(
        "Tarjeta", back_populates="sprint", lazy="raise"
    )
    progresos: Mapped[list["ProgresoSprint"]] = relationship(
        "ProgresoSprint", back_populates="sprint", lazy="raise"
    )
    intentos: Mapped[list["Intento"]] = relationship(
        "Intento", back_populates="sprint", lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint("modulo_id", "orden", name="uq_sprints_modulo_orden"),
        CheckConstraint(
            "ini_presupuesto BETWEEN 0 AND 100",
            name="ck_sprints_ini_presupuesto",
        ),
        CheckConstraint(
            "ini_reputacion BETWEEN 0 AND 100",
            name="ck_sprints_ini_reputacion",
        ),
        CheckConstraint(
            "ini_velocidad BETWEEN 0 AND 100",
            name="ck_sprints_ini_velocidad",
        ),
        CheckConstraint(
            "ini_riesgo BETWEEN 0 AND 100",
            name="ck_sprints_ini_riesgo",
        ),
        CheckConstraint(
            "escenario_jefe IS NULL OR es_examen = true",
            name="ck_sprints_escenario_solo_examen",
        ),
    )


class Tarjeta(Base):
    __tablename__ = "tarjetas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sprint_id: Mapped[int] = mapped_column(Integer, ForeignKey("sprints.id"), nullable=False)

    tipo: Mapped[TipoTarjeta] = mapped_column(
        SAEnum(TipoTarjeta, name="tipo_tarjeta", create_type=False),
        nullable=False,
    )
    categoria: Mapped[str] = mapped_column(String(60), nullable=False)
    personaje_nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    personaje_rol: Mapped[str] = mapped_column(String(60), nullable=False)
    iniciales: Mapped[str] = mapped_column(String(3), nullable=False)

    texto: Mapped[str] = mapped_column(Text, nullable=False)
    explicacion: Mapped[str] = mapped_column(Text, nullable=False)
    nota_abogado: Mapped[str | None] = mapped_column(Text, nullable=True)

    array_palabras_trampa: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    contenido_interactivo: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    actualizado_en: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    sprint: Mapped["Sprint"] = relationship("Sprint", back_populates="tarjetas", lazy="raise")
    respuestas: Mapped[list["Respuesta"]] = relationship(
        "Respuesta", back_populates="tarjeta", lazy="raise"
    )
    apelaciones: Mapped[list["Apelacion"]] = relationship(
        "Apelacion", back_populates="tarjeta", lazy="raise"
    )

    __table_args__ = (Index("ix_tarjetas_sprint_activa_tipo", "sprint_id", "activa", "tipo"),)
