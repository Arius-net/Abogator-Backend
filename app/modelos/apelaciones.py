from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.modelos.base import Base
from app.modelos.enums import EstadoApelacion, ResultadoRespuesta, Veredicto

if TYPE_CHECKING:
    from app.modelos.usuarios import Usuario
    from app.modelos.contenido import Tarjeta
    from app.modelos.juego import Respuesta


class Apelacion(Base):
    __tablename__ = "apelaciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    tarjeta_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tarjetas.id"), nullable=False
    )
    tarjeta_version: Mapped[int] = mapped_column(Integer, nullable=False)
    respuesta_origen_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("respuestas.id"), nullable=True
    )
    etapa: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    proxima_revision: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[EstadoApelacion] = mapped_column(
        SAEnum(EstadoApelacion, name="estado_apelacion", create_type=False),
        nullable=False,
        default=EstadoApelacion.pendiente,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="apelaciones", lazy="raise")
    tarjeta: Mapped["Tarjeta"] = relationship("Tarjeta", back_populates="apelaciones", lazy="raise")
    respuesta_origen: Mapped["Respuesta | None"] = relationship(
        "Respuesta", back_populates="apelaciones", lazy="raise"
    )
    juicios: Mapped[list["JuicioApelacion"]] = relationship(
        "JuicioApelacion", back_populates="apelacion", lazy="raise"
    )

    __table_args__ = (
        CheckConstraint("etapa BETWEEN 1 AND 3", name="ck_apelaciones_etapa"),
        Index(
            "ix_apelacion_abierta",
            "usuario_id",
            "tarjeta_id",
            unique=True,
            postgresql_where=text("estado = 'pendiente'"),
        ),
        Index(
            "ix_apelaciones_buzon",
            "usuario_id",
            "estado",
            "proxima_revision",
        ),
    )


class JuicioApelacion(Base):
    __tablename__ = "juicios_apelacion"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    apelacion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("apelaciones.id"), nullable=False
    )
    veredicto: Mapped[Veredicto | None] = mapped_column(
        SAEnum(Veredicto, name="veredicto", create_type=False), nullable=True
    )
    resultado: Mapped[ResultadoRespuesta] = mapped_column(
        SAEnum(ResultadoRespuesta, name="resultado_respuesta", create_type=False),
        nullable=False,
    )
    vida_recuperada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resuelto_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    apelacion: Mapped["Apelacion"] = relationship(
        "Apelacion", back_populates="juicios", lazy="raise"
    )


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    titulo: Mapped[str] = mapped_column(String(80), nullable=False)
    cuerpo: Mapped[str] = mapped_column(String(200), nullable=False)
    referencia_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    programada_para: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    enviada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="pendiente")

    usuario: Mapped["Usuario"] = relationship(
        "Usuario", back_populates="notificaciones", lazy="raise"
    )

    __table_args__ = (Index("ix_notificaciones_estado_programada", "estado", "programada_para"),)
