from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_config
from app.core.db import cerrar_engine
from app.core.errores import ErrorNegocio, handler_error_negocio

from app.dominios.admin.router import router as admin_router
from app.dominios.apelaciones.router import router as apelaciones_router
from app.dominios.auth.router import router as auth_router
from app.dominios.contenido.router import router as contenido_router
from app.dominios.juego.router import router as juego_router
from app.dominios.sync.router import router as sync_router
from app.dominios.tienda.router import router as tienda_router
from app.dominios.usuarios.router import router as usuarios_router


async def verificar_conexion_db() -> bool:
    from sqlalchemy import text
    from app.core.db import _get_session_factory
    async with _get_session_factory()() as s:
        await s.execute(text("SELECT 1"))
    return True


async def verificar_conexion_redis() -> bool:
    try:
        import redis.asyncio as aioredis
    except ImportError:
        return False
    r = aioredis.from_url(get_config().REDIS_URL, socket_timeout=1.0)
    try:
        await r.ping()
        return True
    finally:
        await r.aclose()


def crear_app() -> FastAPI:
    cfg = get_config()

    app = FastAPI(
        title="AboGator Backend",
        version="0.1.0",
        docs_url="/v1/docs",
        openapi_url="/v1/openapi.json",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[cfg.API_BASE_URL] if cfg.API_BASE_URL else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:8]}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    app.add_exception_handler(ErrorNegocio, handler_error_negocio)  # type: ignore[arg-type]

    @app.exception_handler(RequestValidationError)
    async def handler_error_validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "")
        campos = []
        for err in exc.errors():
            loc = " -> ".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", "Dato inválido")
            campos.append({"campo": loc, "error": msg})
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "codigo": "VALIDACION",
                    "mensaje": "Los datos enviados son inválidos.",
                    "detalle": {"campos": campos},
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handler_error_interno(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "codigo": "ERROR_INTERNO",
                    "mensaje": "Ocurrió un error interno. Intenta más tarde.",
                    "detalle": None,
                    "request_id": request_id,
                }
            },
        )

    @app.on_event("shutdown")
    async def shutdown() -> None:
        from app.core.redis_client import cerrar_redis
        await cerrar_engine()
        await cerrar_redis()

    @app.get("/v1/salud", tags=["infraestructura"], summary="Health check", response_model=None)
    async def salud() -> JSONResponse:
        """Verifica que la API, la base de datos y Redis estén disponibles (09 §2)."""
        import asyncio

        estado: dict[str, str] = {"api": "ok", "base_datos": "error", "redis": "error"}

        try:
            await asyncio.wait_for(verificar_conexion_db(), timeout=1.0)
            estado["base_datos"] = "ok"
        except Exception:
            pass

        try:
            await asyncio.wait_for(verificar_conexion_redis(), timeout=1.0)
            estado["redis"] = "ok"
        except Exception:
            pass

        http_status = 200 if all(v == "ok" for v in estado.values()) else 503
        return JSONResponse(content=estado, status_code=http_status)

    app.include_router(auth_router, prefix="/v1/auth", tags=["auth"])
    app.include_router(usuarios_router, prefix="/v1", tags=["cuenta"])
    app.include_router(contenido_router, prefix="/v1", tags=["contenido"])
    app.include_router(admin_router, prefix="/v1/admin", tags=["admin"])
    app.include_router(juego_router, prefix="/v1", tags=["juego"])
    app.include_router(sync_router, prefix="/v1", tags=["sync"])
    app.include_router(tienda_router, prefix="/v1", tags=["tienda"])
    app.include_router(apelaciones_router, prefix="/v1", tags=["apelaciones"])

    return app


app = crear_app()
