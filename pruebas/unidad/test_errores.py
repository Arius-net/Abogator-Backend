import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.core.errores import (
    ErrorNegocio,
    SinVidas,
    SprintBloqueado,
    DemasiasiasPeticiones,
    handler_error_negocio,
)

def test_excepciones_negocio_atributos() -> None:
    exc = SinVidas(detalle={"proxima_vida_en": "2026-11-16T20:00:00Z"})
    assert exc.http_status == 403
    assert exc.codigo == "SIN_VIDAS"
    assert exc.detalle == {"proxima_vida_en": "2026-11-16T20:00:00Z"}
    assert "vidas" in exc.mensaje.lower()

def test_formato_respuesta_error_negocio() -> None:
    app = FastAPI()
    app.add_exception_handler(ErrorNegocio, handler_error_negocio)  # type: ignore[arg-type]

    @app.middleware("http")
    async def req_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = "req_test123"
        return await call_next(request)

    @app.get("/test-error")
    def ruta_con_error() -> None:
        raise SprintBloqueado(detalle={"motivo": "contenido_insuficiente"})

    @app.get("/test-rate-limit")
    def ruta_rate_limit() -> None:
        raise DemasiasiasPeticiones(detalle={"retry_after": 60})

    client = TestClient(app)
    
    resp = client.get("/test-error")
    assert resp.status_code == 403
    data = resp.json()
    assert "error" in data
    assert data["error"]["codigo"] == "SPRINT_BLOQUEADO"
    assert data["error"]["detalle"] == {"motivo": "contenido_insuficiente"}
    assert data["error"]["request_id"] == "req_test123"

    resp_rl = client.get("/test-rate-limit")
    assert resp_rl.status_code == 429
    assert resp_rl.headers.get("retry-after") == "60"
    assert resp_rl.json()["error"]["codigo"] == "DEMASIADAS_PETICIONES"
