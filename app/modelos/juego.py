from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.modelos.base import Base
from app.modelos.enums import (
    EstadoIntento,
    EstadoProgreso,
    ResultadoRespuesta,
    TipoIntento,
    Veredicto,
)

if TYPE_CHECKING:
    from app.modelos.contenido import Sprint, Tarjeta
    from app.modelos.usuarios import Usuario
    from app.modelos.apelaciones import Apelacion
    from app.modelos.logros import Certificado


class ProgresoSprint(Base):
    __tablename__ = "progreso_sprints"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), primary_key=True
    )
    sprint_id: Mapped[int] = mapped_column(Integer, ForeignKey("sprints.id"), primary_key=True)
    estado: Mapped[EstadoProgreso] = mapped_column(
        SAEnum(EstadoProgreso, name="estado_progreso", create_type=False),
        nullable=False,
        default=EstadoProgreso.bloqueado,
    )
    estrellas: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    mejor_aciertos: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    perfecto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="progresos", lazy="raise")
    sprint: Mapped["Sprint"] = relationship("Sprint", back_populates="progresos", lazy="raise")

    __table_args__ = (CheckConstraint("estrellas BETWEEN 0 AND 3", name="ck_progreso_estrellas"),)


class Intento(Base):
    __tablename__ = "intentos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    sprint_id: Mapped[int] = mapped_column(Integer, ForeignKey("sprints.id"), nullable=False)
    tipo: Mapped[TipoIntento] = mapped_column(
        SAEnum(TipoIntento, name="tipo_intento", create_type=False), nullable=False
    )
    estado: Mapped[EstadoIntento] = mapped_column(
        SAEnum(EstadoIntento, name="estado_intento", create_type=False),
        nullable=False,
        default=EstadoIntento.en_curso,
    )

    ind_presupuesto: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ind_reputacion: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ind_velocidad: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ind_riesgo: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    hp_jefe: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    aciertos: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    parciales: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    errores: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    xp_ganada: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    monedas_ganadas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tarjetas_asignadas: Mapped[list[dict[str, Any]] | dict[str, Any]] = mapped_column(
        JSONB, nullable=False
    )

    marcado_revision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pausado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pausa_acumulada_s: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    iniciado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    terminado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="intentos", lazy="raise")
    sprint: Mapped["Sprint"] = relationship("Sprint", back_populates="intentos", lazy="raise")
    respuestas: Mapped[list["Respuesta"]] = relationship(
        "Respuesta", back_populates="intento", lazy="raise"
    )
    certificados: Mapped[list["Certificado"]] = relationship(
        "Certificado", back_populates="intento", lazy="raise"
    )

    __table_args__ = (
        CheckConstraint("ind_presupuesto BETWEEN 0 AND 100", name="ck_intentos_ind_presupuesto"),
        CheckConstraint("ind_reputacion BETWEEN 0 AND 100", name="ck_intentos_ind_reputacion"),
        CheckConstraint("ind_velocidad BETWEEN 0 AND 100", name="ck_intentos_ind_velocidad"),
        CheckConstraint("ind_riesgo BETWEEN 0 AND 100", name="ck_intentos_ind_riesgo"),
        CheckConstraint(
            "hp_jefe IS NULL OR hp_jefe BETWEEN 0 AND 100",
            name="ck_intentos_hp_jefe",
        ),
        CheckConstraint("pausa_acumulada_s >= 0", name="ck_intentos_pausa_acumulada_s"),
        Index(
            "ix_intentos_en_curso",
            "usuario_id",
            unique=True,
            postgresql_where=text("estado = 'en_curso'"),
        ),
        Index("ix_intentos_usuario_id", "usuario_id"),
    )


class Respuesta(Base):
    __tablename__ = "respuestas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    intento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intentos.id"), nullable=False
    )
    tarjeta_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tarjetas.id"), nullable=False
    )

    veredicto: Mapped[Veredicto | None] = mapped_column(
        SAEnum(Veredicto, name="veredicto", create_type=False), nullable=True
    )
    resultado: Mapped[ResultadoRespuesta] = mapped_column(
        SAEnum(ResultadoRespuesta, name="resultado_respuesta", create_type=False),
        nullable=False,
    )
    segundos: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    por_que_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evidencia_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    justificacion_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    contraargumento_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    amparo_usado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    d_presupuesto: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    d_reputacion: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    d_velocidad: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    d_riesgo: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    monedas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vidas_delta: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    respondido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recibido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    intento: Mapped["Intento"] = relationship("Intento", back_populates="respuestas", lazy="raise")
    tarjeta: Mapped["Tarjeta"] = relationship("Tarjeta", back_populates="respuestas", lazy="raise")
    apelaciones: Mapped[list["Apelacion"]] = relationship(
        "Apelacion", back_populates="respuesta_origen", lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint("intento_id", "tarjeta_id", name="uq_respuestas_intento_tarjeta"),
        Index("ix_respuestas_intento_id", "intento_id"),
    )
