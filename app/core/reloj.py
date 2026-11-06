from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable


_now_fn: Callable[[], datetime] = lambda: datetime.now(tz=timezone.utc)


def now() -> datetime:
    """Devuelve la hora actual del servidor en UTC.

    Sustituible en pruebas::

        import app.core.reloj as reloj
        reloj._now_fn = lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
    """
    return _now_fn()


def set_reloj(fn: Callable[[], datetime]) -> None:
    """Sustituye la función de reloj (solo para pruebas)."""
    global _now_fn
    _now_fn = fn


def reset_reloj() -> None:
    """Restaura el reloj real (usar en teardown de pruebas)."""
    global _now_fn
    _now_fn = lambda: datetime.now(tz=timezone.utc)
