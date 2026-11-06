from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_config

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        cfg = get_config()
        _engine = create_async_engine(
            cfg.DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            connect_args={"timeout": 2},
        )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def get_sesion() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia FastAPI que provee una sesión por petición."""
    async with _get_session_factory()() as sesion:
        yield sesion


async def cerrar_engine() -> None:
    """Cierra el engine al apagar la aplicación."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
