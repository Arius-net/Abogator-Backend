from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.modelos.base import Base

if TYPE_CHECKING:
    from app.modelos.usuarios import Usuario
    from app.modelos.contenido import Modulo
    from app.modelos.juego import Intento


class Insignia(Base):
    __tablename__ = "insignias"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    clave: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    icono: Mapped[str] = mapped_column(String(40), nullable=False)

    usuarios: Mapped[list["UsuarioInsignia"]] = relationship(
        "UsuarioInsignia", back_populates="insignia", lazy="raise"
    )


class UsuarioInsignia(Base):
    __tablename__ = "usuario_insignias"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), primary_key=True
    )
    insignia_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("insignias.id"), primary_key=True
    )
    obtenida_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    usuario: Mapped["Usuario"] = relationship(
        "Usuario", back_populates="insignias", lazy="raise"
    )
    insignia: Mapped["Insignia"] = relationship(
        "Insignia", back_populates="usuarios", lazy="raise"
    )


class Certificado(Base):
    __tablename__ = "certificados"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    modulo_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("modulos.id"), nullable=False
    )
    intento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intentos.id"), nullable=False
    )
    folio: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    emitido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    usuario: Mapped["Usuario"] = relationship(
        "Usuario", back_populates="certificados", lazy="raise"
    )
    modulo: Mapped["Modulo"] = relationship(
        "Modulo", back_populates="certificados", lazy="raise"
    )
    intento: Mapped["Intento"] = relationship(
        "Intento", back_populates="certificados", lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint("usuario_id", "modulo_id", name="uq_certificados_usuario_modulo"),
    )
