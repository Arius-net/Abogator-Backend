from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_request_id_middleware_genera_id() -> None:
    with (
        patch("app.main.verificar_conexion_db", new_callable=AsyncMock) as m_db,
        patch("app.main.verificar_conexion_redis", new_callable=AsyncMock) as m_redis,
    ):
        m_db.return_value = True
        m_redis.return_value = True
        resp = client.get("/v1/salud")
        assert "X-Request-ID" in resp.headers
        assert resp.headers["X-Request-ID"].startswith("req_")


def test_request_id_middleware_respeta_id_cliente() -> None:
    custom_id = "req_cliente_custom_999"
    with (
        patch("app.main.verificar_conexion_db", new_callable=AsyncMock) as m_db,
        patch("app.main.verificar_conexion_redis", new_callable=AsyncMock) as m_redis,
    ):
        m_db.return_value = True
        m_redis.return_value = True
        resp = client.get("/v1/salud", headers={"X-Request-ID": custom_id})
        assert resp.headers.get("X-Request-ID") == custom_id


def test_salud_servicios_disponibles_retorna_200() -> None:
    with (
        patch("app.main.verificar_conexion_db", new_callable=AsyncMock) as m_db,
        patch("app.main.verificar_conexion_redis", new_callable=AsyncMock) as m_redis,
    ):
        m_db.return_value = True
        m_redis.return_value = True
        resp = client.get("/v1/salud")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"api": "ok", "base_datos": "ok", "redis": "ok"}


def test_salud_servicios_caidos_retorna_503() -> None:
    with (
        patch("app.main.verificar_conexion_db", new_callable=AsyncMock) as m_db,
        patch("app.main.verificar_conexion_redis", new_callable=AsyncMock) as m_redis,
    ):
        m_db.side_effect = Exception("Conexión rechazada")
        m_redis.side_effect = Exception("Redis inalcanzable")
        resp = client.get("/v1/salud")
        assert resp.status_code == 503
        data = resp.json()
        assert data["api"] == "ok"
        assert data["base_datos"] == "error"
        assert data["redis"] == "error"
