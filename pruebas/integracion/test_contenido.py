from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.deps import usuario_actual
from app.dominios.contenido.servicio import ContenidoServicio
from app.esquemas.admin import (
    ModuloProgresoRespuesta,
    SprintIntroRespuesta,
    SprintRespuesta,
)
from app.main import app

client = TestClient(app)
USUARIO_ID_TEST = uuid.uuid4()


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[usuario_actual] = lambda: {
        "sub": str(USUARIO_ID_TEST),
        "rol": "jugador",
        "perfil": "desarrollador",
    }
    yield
    app.dependency_overrides.pop(usuario_actual, None)


class TestContenidoEndpoints:
    def test_listar_modulos_con_progreso(self) -> None:
        mock_data = [
            ModuloProgresoRespuesta(
                id=1,
                numero=1,
                titulo="Protección de datos",
                etapa_startup="Del Garage al MVP",
                color_token="modulo-1",
                activo=True,
                sprints_completados=2,
                total_sprints=6,
                examen_aprobado=False,
            )
        ]
        with patch.object(
            ContenidoServicio, "listar_modulos_con_progreso", new_callable=AsyncMock
        ) as m_mod:
            m_mod.return_value = mock_data
            resp = client.get("/v1/modulos")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["titulo"] == "Protección de datos"
        assert data[0]["sprints_completados"] == 2

    def test_listar_sprints_de_modulo(self) -> None:
        mock_data = [
            SprintRespuesta(
                id=1,
                modulo_id=1,
                orden=1,
                es_examen=False,
                titulo="Módulo 1 · Sprint 1",
                objetivo="Objetivo 1",
                estado="disponible",
                estrellas=3,
                mejor_aciertos=10,
                perfecto=True,
            )
        ]
        with patch.object(
            ContenidoServicio, "listar_sprints_de_modulo", new_callable=AsyncMock
        ) as m_sp:
            m_sp.return_value = mock_data
            resp = client.get("/v1/modulos/1/sprints")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["estado"] == "disponible"
        assert data[0]["estrellas"] == 3

    def test_detalle_sprint(self) -> None:
        mock_intro = SprintIntroRespuesta(
            id=1,
            modulo_id=1,
            orden=1,
            es_examen=False,
            titulo="Módulo 1 · Sprint 1",
            objetivo="Objetivo del sprint",
            ini_presupuesto=70,
            ini_reputacion=60,
            ini_velocidad=50,
            ini_riesgo=25,
            monedas_max=60,
        )
        with patch.object(
            ContenidoServicio, "detalle_sprint", new_callable=AsyncMock
        ) as m_det:
            m_det.return_value = mock_intro
            resp = client.get("/v1/sprints/1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["titulo"] == "Módulo 1 · Sprint 1"
        assert data["ini_presupuesto"] == 70
