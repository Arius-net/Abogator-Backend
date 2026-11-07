# pruebas/conftest.py
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock

import pytest

from app.core import reloj
from app.core.db import get_sesion
from app.main import app


@pytest.fixture(autouse=True)
def restablecer_reloj() -> Generator[None, None, None]:
    """Asegura que el reloj vuelva a su estado real tras cada prueba."""
    yield
    reloj.reset_reloj()


@pytest.fixture(autouse=True)
def mock_sesion_db() -> Generator[None, None, None]:
    """
    Sustituye get_sesion por un AsyncMock en todas las pruebas
    para evitar intentar cargar asyncpg o conectar a PostgreSQL.
    """
    async def _mock_sesion():
        yield AsyncMock()

    app.dependency_overrides[get_sesion] = _mock_sesion
    yield
    app.dependency_overrides.pop(get_sesion, None)
