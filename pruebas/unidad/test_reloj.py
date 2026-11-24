from datetime import datetime, timezone
from app.core import reloj


def test_reloj_default_retorna_utc() -> None:
    t = reloj.now()
    assert t.tzinfo is not None
    assert t.tzinfo == timezone.utc


def test_reloj_inyectable() -> None:
    tiempo_fijo = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
    reloj.set_reloj(lambda: tiempo_fijo)
    assert reloj.now() == tiempo_fijo


def test_reloj_reset() -> None:
    tiempo_fijo = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
    reloj.set_reloj(lambda: tiempo_fijo)
    assert reloj.now() == tiempo_fijo
    reloj.reset_reloj()
    assert reloj.now() != tiempo_fijo
