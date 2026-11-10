# pruebas/unidad/test_vidas.py
# Pruebas unitarias para la lógica de regeneración lazy de vidas (05 §5).
# No requiere BD: se prueban las funciones de cálculo directamente.

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import floor

import pytest

from app.core.reloj import set_reloj, reset_reloj
from app.core.config import get_config


def _calcular_estado_vidas(
    vidas_almacenadas: int,
    vidas_base_en: datetime,
    ahora: datetime,
    vidas_max: int,
    regen_segundos: int,
) -> tuple[int, datetime | None]:
    """Extrae la lógica de regen sin depender del servicio completo."""
    delta_s = (ahora - vidas_base_en).total_seconds()
    regeneradas = int(delta_s // regen_segundos)
    vidas_efectivas = min(vidas_max, vidas_almacenadas + regeneradas)

    proxima_vida_en = None
    if vidas_efectivas < vidas_max:
        residuo_s = delta_s % regen_segundos
        proxima_vida_en = ahora + timedelta(seconds=regen_segundos - residuo_s)

    return vidas_efectivas, proxima_vida_en


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRegenLazy:
    def test_tres_vidas_cuatro_horas_llega_a_tope(self) -> None:
        """3 vidas + 4h transcurridas → llega al tope (5), no hay proxima_vida_en."""
        regen = 7200  # 2 h en segundos
        vidas_max = 5
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        ahora = base + timedelta(hours=4)  # 2 vidas regeneradas → 3+2=5

        vidas, proxima = _calcular_estado_vidas(3, base, ahora, vidas_max, regen)

        assert vidas == 5
        assert proxima is None

    def test_cero_vidas_dos_horas_da_una_vida(self) -> None:
        """0 vidas + 2h exactas → exactamente 1 vida regenerada."""
        regen = 7200
        vidas_max = 5
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        ahora = base + timedelta(hours=2)

        vidas, proxima = _calcular_estado_vidas(0, base, ahora, vidas_max, regen)

        assert vidas == 1
        assert proxima is not None
        # Faltan exactamente 2h para la siguiente (0 residuo → 2h completas)
        esperada = ahora + timedelta(seconds=regen)
        assert abs((proxima - esperada).total_seconds()) < 1

    def test_cero_vidas_una_hora_proxima_en_una_hora(self) -> None:
        """0 vidas + 1h transcurrida → 0 regeneradas, proxima_vida_en en 1h."""
        regen = 7200
        vidas_max = 5
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        ahora = base + timedelta(hours=1)  # 1h < 2h → 0 regeneradas

        vidas, proxima = _calcular_estado_vidas(0, base, ahora, vidas_max, regen)

        assert vidas == 0
        assert proxima is not None
        # Residuo = 3600s, faltan 7200-3600 = 3600s = 1h
        assert abs((proxima - (ahora + timedelta(hours=1))).total_seconds()) < 1

    def test_vidas_en_tope_no_genera_proxima(self) -> None:
        """Si ya tiene el tope, proxima_vida_en debe ser None."""
        regen = 7200
        vidas_max = 5
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        ahora = base + timedelta(minutes=30)

        vidas, proxima = _calcular_estado_vidas(5, base, ahora, vidas_max, regen)

        assert vidas == 5
        assert proxima is None

    def test_no_supera_vidas_max(self) -> None:
        """Muchas horas transcurridas nunca superan el tope."""
        regen = 7200
        vidas_max = 5
        base = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        ahora = base + timedelta(days=7)  # 84 regen potenciales

        vidas, proxima = _calcular_estado_vidas(0, base, ahora, vidas_max, regen)

        assert vidas == vidas_max
        assert proxima is None
