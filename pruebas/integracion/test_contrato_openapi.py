from __future__ import annotations

import pytest
from app.main import app


def test_contrato_openapi_rutas_esenciales():
    openapi = app.openapi()
    rutas = openapi.get("paths", {})

    esperadas = [
        "/v1/salud",
        "/v1/auth/registro",
        "/v1/auth/login",
        "/v1/auth/renovar",
        "/v1/auth/logout",
        "/v1/auth/recuperar",
        "/v1/auth/restablecer",
        "/v1/me",
        "/v1/me/estado",
        "/v1/me/preferencias",
        "/v1/me/dispositivos",
        "/v1/me/datos",
        "/v1/modulos",
        "/v1/modulos/{id}/sprints",
        "/v1/sprints/{id}",
        "/v1/sprints/{id}/intentos",
        "/v1/intentos/{id}",
        "/v1/intentos/{id}/respuestas",
        "/v1/intentos/{id}/abandonar",
        "/v1/intentos/{id}/comodines",
        "/v1/examenes/{sprint_id}/intentos",
        "/v1/intentos/{id}/contraargumento",
        "/v1/intentos/{id}/pausa",
        "/v1/intentos/{id}/reanudar",
        "/v1/tienda",
        "/v1/tienda/compras",
        "/v1/apelaciones",
        "/v1/apelaciones/{id}",
        "/v1/apelaciones/{id}/juicios",
        "/v1/sync/respuestas",
        "/v1/admin/tarjetas",
        "/v1/admin/tarjetas/{id}",
        "/v1/admin/tarjetas/{id}/estado",
        "/v1/admin/escenarios",
        "/v1/admin/comodines/{id}",
        "/v1/admin/metricas",
    ]

    for ruta in esperadas:
        assert ruta in rutas, f"Falta la ruta {ruta} en el contrato OpenAPI"


def test_contrato_openapi_version_y_titulo():
    openapi = app.openapi()
    assert openapi["info"]["title"] == "AboGator Backend"
    assert openapi["openapi"].startswith("3.")
