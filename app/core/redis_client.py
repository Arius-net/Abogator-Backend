from __future__ import annotations

from typing import Any

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None  # type: ignore[no-redef]

from app.core.config import get_config

_redis: Any | None = None


def get_redis() -> Any:
    """Devuelve la instancia compartida de Redis (lazy init)."""
    global _redis
    if _redis is None:
        if aioredis is None:
            from unittest.mock import AsyncMock

            return AsyncMock()
        cfg = get_config()
        _redis = aioredis.from_url(
            cfg.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def cerrar_redis() -> None:
    global _redis
    if _redis is not None:
        if hasattr(_redis, "aclose"):
            await _redis.aclose()
        _redis = None
