from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.modelos.base import Base
from app.modelos.enums import EstadoCuenta, PerfilUsuario, RolUsuario

if TYPE_CHECKING:
    from app.modelos.juego import Intento, ProgresoSprint, Respuesta
    from app.modelos.economia import MovimientoEconomia
    from app.modelos.apelaciones import Apelacion, Notificacion
    from app.modelos.logros import Certificado, UsuarioInsignia
    from app.modelos.admin import AuditoriaAdmin


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    correo: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    hash_contrasena: Mapped[str] = mapped_column(String(72), nullable=False)

    perfil: Mapped[PerfilUsuario] = mapped_column(
        SAEnum(PerfilUsuario, name="perfil_usuario", create_type=False),
        nullable=False,
        default=PerfilUsuario.desarrollador,
    )
    rol: Mapped[RolUsuario] = mapped_column(
        SAEnum(RolUsuario, name="rol_usuario", create_type=False),
        nullable=False,
        default=RolUsuario.jugador,
    )
    estado_cuenta: Mapped[EstadoCuenta] = mapped_column(
        SAEnum(EstadoCuenta, name="estado_cuenta", create_type=False),
        nullable=False,
        default=EstadoCuenta.activo,
    )
    zona_horaria: Mapped[str] = mapped_column(
        String(60), nullable=False, default="America/Mexico_City"
    )

    vidas: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=5)
    vidas_base_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    monedas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nivel: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    racha_actual: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    racha_maxima: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ultimo_dia_racha: Mapped[date | None] = mapped_column(Date, nullable=True)
    amparo_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    preferencias: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    inventario: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reto_diario: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ultimo_acceso: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    eliminado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    consentimientos: Mapped[list["Consentimiento"]] = relationship(
        "Consentimiento", back_populates="usuario", lazy="raise"
    )
    sesiones_refresh: Mapped[list["SesionRefresh"]] = relationship(
        "SesionRefresh", back_populates="usuario", lazy="raise"
    )
    restablecimientos: Mapped[list["RestablecimientoContrasena"]] = relationship(
        "RestablecimientoContrasena", back_populates="usuario", lazy="raise"
    )
    dispositivos_push: Mapped[list["DispositivoPush"]] = relationship(
        "DispositivoPush", back_populates="usuario", lazy="raise"
    )
    progresos: Mapped[list["ProgresoSprint"]] = relationship(
        "ProgresoSprint", back_populates="usuario", lazy="raise"
    )
    intentos: Mapped[list["Intento"]] = relationship(
        "Intento", back_populates="usuario", lazy="raise"
    )
    movimientos_economia: Mapped[list["MovimientoEconomia"]] = relationship(
        "MovimientoEconomia", back_populates="usuario", lazy="raise"
    )
    apelaciones: Mapped[list["Apelacion"]] = relationship(
        "Apelacion", back_populates="usuario", lazy="raise"
    )
    notificaciones: Mapped[list["Notificacion"]] = relationship(
        "Notificacion", back_populates="usuario", lazy="raise"
    )
    insignias: Mapped[list["UsuarioInsignia"]] = relationship(
        "UsuarioInsignia", back_populates="usuario", lazy="raise"
    )
    certificados: Mapped[list["Certificado"]] = relationship(
        "Certificado", back_populates="usuario", lazy="raise"
    )
    auditorias: Mapped[list["AuditoriaAdmin"]] = relationship(
        "AuditoriaAdmin", back_populates="admin", lazy="raise"
    )

    __table_args__ = (
        CheckConstraint("vidas BETWEEN 0 AND 5", name="ck_usuarios_vidas"),
        CheckConstraint("monedas >= 0", name="ck_usuarios_monedas"),
        CheckConstraint("xp >= 0", name="ck_usuarios_xp"),
        CheckConstraint("nivel >= 1", name="ck_usuarios_nivel"),
        CheckConstraint("racha_actual >= 0", name="ck_usuarios_racha_actual"),
    )


class Consentimiento(Base):
    __tablename__ = "consentimientos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    documento: Mapped[str] = mapped_column(String(30), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    aceptado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)

    usuario: Mapped["Usuario"] = relationship(
        "Usuario", back_populates="consentimientos", lazy="raise"
    )


class SesionRefresh(Base):
    __tablename__ = "sesiones_refresh"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    dispositivo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expira_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revocado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reemplazado_por: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    usuario: Mapped["Usuario"] = relationship(
        "Usuario", back_populates="sesiones_refresh", lazy="raise"
    )

    __table_args__ = (
        Index("ix_sesiones_refresh_usuario_id", "usuario_id"),
    )


class RestablecimientoContrasena(Base):
    __tablename__ = "restablecimientos_contrasena"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    usuario: Mapped["Usuario"] = relationship(
        "Usuario", back_populates="restablecimientos", lazy="raise"
    )


class DispositivoPush(Base):
    __tablename__ = "dispositivos_push"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    plataforma: Mapped[str] = mapped_column(String(10), nullable=False)
    token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    usuario: Mapped["Usuario"] = relationship(
        "Usuario", back_populates="dispositivos_push", lazy="raise"
    )
