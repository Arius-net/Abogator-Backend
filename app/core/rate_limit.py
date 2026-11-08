from __future__ import annotations

from typing import Any

from app.core.config import get_config
from app.core.errores import DemasiasiasPeticiones


async def _incrementar_contador(
    redis: Any,
    clave: str,
    ventana_seg: int,
    limite: int,
) -> int:
    """
    Contador de ventana fija en Redis.
    Devuelve el valor actual tras incrementar.
    Lanza DemasiasiasPeticiones si se supera el límite.
    """
    pipe = redis.pipeline()
    pipe.incr(clave)
    pipe.expire(clave, ventana_seg)
    resultados = await pipe.execute()
    contador: int = resultados[0]

    if contador > limite:
        ttl: int = await redis.ttl(clave)
        raise DemasiasiasPeticiones(detalle={"retry_after": max(ttl, 1)})

    return contador


async def verificar_rate_login(
    redis: Any,
    ip: str,
    correo: str,
) -> None:
    """10 intentos de login cada 15 min por IP+correo (06 §3)."""
    cfg = get_config()
    clave = f"rl:login:{ip}:{correo.lower()}"
    ventana = cfg.LOGIN_VENTANA_MIN * 60
    await _incrementar_contador(redis, clave, ventana, cfg.LOGIN_MAX_INTENTOS)


async def verificar_rate_usuario(
    redis: Any,
    usuario_id: str,
) -> None:
    """120 peticiones por minuto por usuario autenticado (06 §3)."""
    cfg = get_config()
    clave = f"rl:usr:{usuario_id}"
    await _incrementar_contador(redis, clave, 60, cfg.RATE_LIMIT_USUARIO_MIN)
