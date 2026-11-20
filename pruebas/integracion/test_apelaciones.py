from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.core.deps import usuario_actual
from app.core.reloj import now
from app.dominios.apelaciones.servicio import ApelacionesServicio
from app.esquemas.apelaciones import EnviarJuicioInput
from app.main import app
from app.modelos.apelaciones import Apelacion, JuicioApelacion
from app.modelos.contenido import Tarjeta
from app.modelos.enums import (
    EstadoApelacion,
    EstadoCuenta,
    PerfilUsuario,
    ResultadoRespuesta,
    RolUsuario,
    TipoTarjeta,
    Veredicto,
)
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


def _crear_usuario(vidas: int = 4) -> Usuario:
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
        vidas=vidas,
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


def _crear_tarjeta(tid: uuid.UUID, version: int = 1, texto: str = "Texto v1") -> Tarjeta:
    return Tarjeta(
        id=tid,
        version=version,
        sprint_id=1,
        tipo=TipoTarjeta.normal,
        categoria="datos",
        personaje_nombre="Dev",
        personaje_rol="Frontend",
        iniciales="DEV",
        texto=texto,
        explicacion="Exp",
        contenido_interactivo={
            "veredictos": {
                "legal": {"resultado": "correcto"},
                "ilegal": {"resultado": "incorrecto"},
                "condicional": {"resultado": "parcial"},
                "escalar": {"resultado": "incorrecto"},
            }
        },
        activa=True,
    )


def test_obtener_buzon_apelaciones():
    ahora = now()
    ap_vencida = Apelacion(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        tarjeta_id=uuid.uuid4(),
        tarjeta_version=1,
        etapa=1,
        proxima_revision=ahora - timedelta(days=1),
        estado=EstadoApelacion.pendiente,
    )
    ap_proxima = Apelacion(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        tarjeta_id=uuid.uuid4(),
        tarjeta_version=1,
        etapa=2,
        proxima_revision=ahora + timedelta(days=5),
        estado=EstadoApelacion.pendiente,
    )

    sesion_mock = AsyncMock()
    servicio = ApelacionesServicio(sesion_mock)
    servicio._repo.listar_apelaciones_pendientes = AsyncMock(return_value=[ap_vencida, ap_proxima])

    with patch("app.dominios.apelaciones.router.ApelacionesServicio", return_value=servicio):
        resp = client.get("/v1/apelaciones")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["vencidas"]) == 1
        assert len(data["proximas"]) == 1
        assert data["vencidas"][0]["id"] == str(ap_vencida.id)
        assert data["proximas"][0]["id"] == str(ap_proxima.id)


def test_obtener_detalle_apelacion_vencida_y_sobrevive_edicion_tarjeta():
    ahora = now()
    tid = uuid.uuid4()
    ap = Apelacion(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        tarjeta_id=tid,
        tarjeta_version=1,
        etapa=1,
        proxima_revision=ahora - timedelta(hours=2),
        estado=EstadoApelacion.pendiente,
    )
    tarjeta_v1 = _crear_tarjeta(tid, version=1, texto="Texto Version 1 Original")

    sesion_mock = AsyncMock()
    servicio = ApelacionesServicio(sesion_mock)
    servicio._repo.buscar_apelacion_por_id = AsyncMock(return_value=ap)
    servicio._repo.buscar_tarjeta_version = AsyncMock(return_value=tarjeta_v1)

    with patch("app.dominios.apelaciones.router.ApelacionesServicio", return_value=servicio):
        resp = client.get(f"/v1/apelaciones/{ap.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tarjeta_version"] == 1
        assert data["texto"] == "Texto Version 1 Original"
        servicio._repo.buscar_tarjeta_version.assert_awaited_once_with(tid, 1)


def test_obtener_detalle_apelacion_no_vencida_retorna_400():
    ahora = now()
    ap = Apelacion(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        tarjeta_id=uuid.uuid4(),
        tarjeta_version=1,
        etapa=1,
        proxima_revision=ahora + timedelta(days=2),
        estado=EstadoApelacion.pendiente,
    )

    sesion_mock = AsyncMock()
    servicio = ApelacionesServicio(sesion_mock)
    servicio._repo.buscar_apelacion_por_id = AsyncMock(return_value=ap)

    with patch("app.dominios.apelaciones.router.ApelacionesServicio", return_value=servicio):
        resp = client.get(f"/v1/apelaciones/{ap.id}")
        assert resp.status_code == 400
        assert resp.json()["error"]["codigo"] == "PETICION_INVALIDA"


def test_resolver_juicio_ganado_etapa1_a_etapa2():
    ahora = now()
    tid = uuid.uuid4()
    usuario = _crear_usuario(vidas=4)
    ap = Apelacion(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        tarjeta_id=tid,
        tarjeta_version=1,
        etapa=1,
        proxima_revision=ahora - timedelta(days=1),
        estado=EstadoApelacion.pendiente,
    )
    tarjeta = _crear_tarjeta(tid, version=1)

    sesion_mock = AsyncMock()
    servicio = ApelacionesServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_apelacion_con_lock = AsyncMock(return_value=ap)
    servicio._repo.buscar_juicio_por_id = AsyncMock(return_value=None)
    servicio._repo.buscar_tarjeta_version = AsyncMock(return_value=tarjeta)
    servicio._repo.crear_juicio = AsyncMock()

    with patch("app.dominios.apelaciones.router.ApelacionesServicio", return_value=servicio):
        resp = client.post(
            f"/v1/apelaciones/{ap.id}/juicios",
            json={"veredicto": "legal"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resultado"] == "correcto"
        assert data["etapa"] == 2
        assert data["vida_recuperada"] is False
        assert ap.etapa == 2


def test_resolver_juicio_ganado_etapa3_cierra_y_recupera_vida():
    ahora = now()
    tid = uuid.uuid4()
    usuario = _crear_usuario(vidas=3)
    ap = Apelacion(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        tarjeta_id=tid,
        tarjeta_version=1,
        etapa=3,
        proxima_revision=ahora - timedelta(days=1),
        estado=EstadoApelacion.pendiente,
    )
    tarjeta = _crear_tarjeta(tid, version=1)

    sesion_mock = AsyncMock()
    servicio = ApelacionesServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_apelacion_con_lock = AsyncMock(return_value=ap)
    servicio._repo.buscar_juicio_por_id = AsyncMock(return_value=None)
    servicio._repo.buscar_tarjeta_version = AsyncMock(return_value=tarjeta)
    servicio._repo.crear_juicio = AsyncMock()
    servicio._repo.crear_movimiento_economia = AsyncMock()

    with patch("app.dominios.apelaciones.router.ApelacionesServicio", return_value=servicio):
        resp = client.post(
            f"/v1/apelaciones/{ap.id}/juicios",
            json={"veredicto": "legal"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resultado"] == "correcto"
        assert data["vida_recuperada"] is True
        assert data["estado"] == "ganada"
        assert usuario.vidas == 4
        servicio._repo.crear_movimiento_economia.assert_awaited_once()


def test_resolver_juicio_perdido_vuelve_a_etapa1():
    ahora = now()
    tid = uuid.uuid4()
    usuario = _crear_usuario(vidas=3)
    ap = Apelacion(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        tarjeta_id=tid,
        tarjeta_version=1,
        etapa=2,
        proxima_revision=ahora - timedelta(days=1),
        estado=EstadoApelacion.pendiente,
    )
    tarjeta = _crear_tarjeta(tid, version=1)

    sesion_mock = AsyncMock()
    servicio = ApelacionesServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_apelacion_con_lock = AsyncMock(return_value=ap)
    servicio._repo.buscar_juicio_por_id = AsyncMock(return_value=None)
    servicio._repo.buscar_tarjeta_version = AsyncMock(return_value=tarjeta)
    servicio._repo.crear_juicio = AsyncMock()

    with patch("app.dominios.apelaciones.router.ApelacionesServicio", return_value=servicio):
        resp = client.post(
            f"/v1/apelaciones/{ap.id}/juicios",
            json={"veredicto": "ilegal"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resultado"] == "incorrecto"
        assert data["vida_recuperada"] is False
        assert ap.etapa == 1
        assert usuario.vidas == 3


def test_resolver_juicio_idempotente():
    ahora = now()
    jid = uuid.uuid4()
    usuario = _crear_usuario(vidas=4)
    ap = Apelacion(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        tarjeta_id=uuid.uuid4(),
        tarjeta_version=1,
        etapa=2,
        proxima_revision=ahora - timedelta(days=1),
        estado=EstadoApelacion.pendiente,
    )
    juicio_guardado = JuicioApelacion(
        id=jid,
        apelacion_id=ap.id,
        veredicto=Veredicto.legal,
        resultado=ResultadoRespuesta.correcto,
        vida_recuperada=False,
        resuelto_en=ahora,
    )

    sesion_mock = AsyncMock()
    servicio = ApelacionesServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_apelacion_con_lock = AsyncMock(return_value=ap)
    servicio._repo.buscar_juicio_por_id = AsyncMock(return_value=juicio_guardado)

    with patch("app.dominios.apelaciones.router.ApelacionesServicio", return_value=servicio):
        resp = client.post(
            f"/v1/apelaciones/{ap.id}/juicios",
            json={"id": str(jid), "veredicto": "legal"},
        )
        assert resp.status_code == 200
        assert resp.json()["resultado"] == "correcto"
