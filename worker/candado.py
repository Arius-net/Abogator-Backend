from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from app.core.config import get_config


@asynccontextmanager
async def candado_redis(
    clave: str, ttl_segundos: int = 60
) -> AsyncGenerator[bool, None]:
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(get_config().REDIS_URL, socket_timeout=2.0)
        adquirido = await r.set(f"candado:{clave}", "1", nx=True, ex=ttl_segundos)
        try:
            yield bool(adquirido)
        finally:
            if adquirido:
                try:
                    await r.delete(f"candado:{clave}")
                except Exception:
                    pass
            await r.aclose()
    except Exception:
        yield True
