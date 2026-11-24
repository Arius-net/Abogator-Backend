from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.deps import usuario_actual
from app.core.reloj import now
from app.dominios.sync.servicio import SyncServicio
from app.main import app
from app.modelos.contenido import Sprint, Tarjeta
from app.modelos.enums import (
    EstadoCuenta,
    EstadoIntento,
    PerfilUsuario,
    ResultadoRespuesta,
    RolUsuario,
    TipoIntento,
    TipoTarjeta,
)
from app.modelos.juego import Intento, Respuesta
from app.modelos.usuarios import Usuario

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


def _crear_usuario() -> Usuario:
    return Usuario(
        id=USUARIO_ID_TEST,
        nombre="Dev User",
        correo="dev@abogator.io",
        hash_contrasena="hash",
        perfil=PerfilUsuario.desarrollador,
        rol=RolUsuario.jugador,
        monedas=100,
        xp=50,
        nivel=1,
        vidas=5,
        vidas_base_en=now(),
        amparo_activo=False,
        racha_actual=1,
        racha_maxima=1,
        ultimo_dia_racha=now().date(),
        zona_horaria="America/Mexico_City",
        preferencias={},
        inventario={"lupa": 0, "abogado": 0, "amparo": 0, "congelar_racha": 0},
        reto_diario={},
        estado_cuenta=EstadoCuenta.activo,
    )


def test_sync_lote_con_duplicada_y_rechazada():
    usuario = _crear_usuario()
    intento_id_abierto = uuid.uuid4()
    intento_id_cerrado = uuid.uuid4()

    resp_duplicada_id = uuid.uuid4()
    resp_cerrada_id = uuid.uuid4()

    intento_cerrado = Intento(
        id=intento_id_cerrado,
        usuario_id=USUARIO_ID_TEST,
        sprint_id=1,
        tipo=TipoIntento.sprint,
        estado=EstadoIntento.completado,
    )

    sesion_mock = AsyncMock()
    servicio = SyncServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)

    async def mock_buscar_resp(rid):
        if rid == resp_duplicada_id:
            return Respuesta(
                id=resp_duplicada_id,
                intento_id=intento_id_abierto,
                tarjeta_id=uuid.uuid4(),
                resultado=ResultadoRespuesta.correcto,
            )
        return None

    async def mock_buscar_intento(iid):
        if iid == intento_id_cerrado:
            return intento_cerrado
        return None

    servicio._repo.buscar_respuesta_por_id = AsyncMock(side_effect=mock_buscar_resp)
    servicio._repo.buscar_intento_por_id = AsyncMock(side_effect=mock_buscar_intento)

    with patch("app.dominios.sync.router.SyncServicio", return_value=servicio):
        resp = client.post(
            "/v1/sync/respuestas",
            json={
                "respuestas": [
                    {
                        "id": str(resp_duplicada_id),
                        "intento_id": str(intento_id_abierto),
                        "tarjeta_id": str(uuid.uuid4()),
                        "veredicto": "legal",
                        "segundos": 4.5,
                    },
                    {
                        "id": str(resp_cerrada_id),
                        "intento_id": str(intento_id_cerrado),
                        "tarjeta_id": str(uuid.uuid4()),
                        "veredicto": "ilegal",
                        "segundos": 5.0,
                    },
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["resultados"]) == 2
        assert data["resultados"][0]["id"] == str(resp_duplicada_id)
        assert data["resultados"][0]["estado"] == "duplicada"
        assert data["resultados"][1]["id"] == str(resp_cerrada_id)
        assert data["resultados"][1]["estado"] == "rechazada"
        assert data["resultados"][1]["motivo"] == "INTENTO_CERRADO"
        assert data["jugador"]["vidas"] == 5


def test_sync_rechaza_lote_mayor_a_50():
    items = [
        {
            "id": str(uuid.uuid4()),
            "intento_id": str(uuid.uuid4()),
            "tarjeta_id": str(uuid.uuid4()),
            "veredicto": "legal",
            "segundos": 2.0,
        }
        for _ in range(51)
    ]
    resp = client.post("/v1/sync/respuestas", json={"respuestas": items})
    assert resp.status_code == 422
