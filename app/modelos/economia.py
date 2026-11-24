from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, TYPE_CHECKING

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
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.modelos.base import Base
from app.modelos.enums import TipoComodin

if TYPE_CHECKING:
    from app.modelos.usuarios import Usuario


class Comodin(Base):
    __tablename__ = "comodines"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    clave: Mapped[TipoComodin] = mapped_column(
        SAEnum(TipoComodin, name="tipo_comodin", create_type=False),
        unique=True,
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(40), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    precio: Mapped[int] = mapped_column(Integer, nullable=False)
    permitido_en_examen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MovimientoEconomia(Base):
    __tablename__ = "movimientos_economia"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    recurso: Mapped[str] = mapped_column(String(10), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    saldo_resultante: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[str] = mapped_column(String(30), nullable=False)
    detalle: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    referencia_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    usuario: Mapped["Usuario"] = relationship(
        "Usuario", back_populates="movimientos_economia", lazy="raise"
    )

    __table_args__ = (
        CheckConstraint(
            "recurso IN ('vidas', 'monedas', 'xp')",
            name="ck_movimientos_recurso",
        ),
        Index("ix_movimientos_hist", "usuario_id", "creado_en"),
    )
