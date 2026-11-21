from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def calcular_programada_para(ahora_utc: datetime, zona_horaria_str: str) -> datetime:
    try:
        tz = ZoneInfo(zona_horaria_str)
    except Exception:
        tz = ZoneInfo("America/Mexico_City")

    hora_local = ahora_utc.astimezone(tz)
    if 9 <= hora_local.hour < 21:
        return ahora_utc
    elif hora_local.hour >= 21:
        manana_local = (hora_local + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        return manana_local.astimezone(timezone.utc)
    else:
        hoy_local = hora_local.replace(hour=9, minute=0, second=0, microsecond=0)
        return hoy_local.astimezone(timezone.utc)
