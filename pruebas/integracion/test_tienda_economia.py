from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.core.deps import usuario_actual
from app.core.errores import (
    ComodinYaUsado,
    IntentoCerrado,
    NoEncontrado,
    PeticionInvalida,
    SaldoInsuficiente,
    SinPermiso,
)
from app.core.reloj import now
from app.dominios.juego.servicio import JuegoServicio
from app.dominios.tienda.servicio import TiendaServicio
from app.esquemas.juego import UsarComodinInput
from app.esquemas.jsonb import Inventario
from app.esquemas.tienda import ComprarComodinInput
from app.main import app
from app.modelos.contenido import Tarjeta
from app.modelos.economia import Comodin
from app.modelos.enums import (
    EstadoCuenta,
    EstadoIntento,
    PerfilUsuario,
    RolUsuario,
    TipoComodin,
    TipoIntento,
    TipoTarjeta,
)
from app.modelos.juego import Intento
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


def _crear_usuario(
    monedas: int = 200,
    inventario: dict | None = None,
    amparo_activo: bool = False,
    racha_actual: int = 0,
    ultimo_dia_racha=None,
) -> Usuario:
    if inventario is None:
        inventario = {"lupa": 1, "abogado": 1, "amparo": 1, "congelar_racha": 0}
    return Usuario(
        id=USUARIO_ID_TEST,
        nombre="Dev User",
        correo="dev@abogator.io",
        hash_contrasena="hash",
        perfil=PerfilUsuario.desarrollador,
        rol=RolUsuario.jugador,
        monedas=monedas,
        xp=0,
        nivel=1,
        vidas=5,
        vidas_base_en=now(),
        amparo_activo=amparo_activo,
        racha_actual=racha_actual,
        racha_maxima=racha_actual,
        ultimo_dia_racha=ultimo_dia_racha,
        zona_horaria="America/Mexico_City",
        preferencias={"modo_oscuro": False, "escala_texto": 1.0, "etiquetas_lector": False, "botones_en_lugar_de_deslizar": False, "haptica": True, "tiempo_extendido": False, "reducir_animaciones": False, "notif_racha": True, "notif_apelaciones": True, "notif_vidas": True},
        inventario=inventario,
        reto_diario={"fecha_reto": "2026-11-21", "tipo": "sprints_completados", "meta": 1, "avance": 0, "completado": False, "recompensa_monedas": 15},
        estado_cuenta=EstadoCuenta.activo,
    )


def test_catalogo_tienda():
    c1 = Comodin(clave=TipoComodin.lupa, nombre="Lupa de Auditor", descripcion="Ver trampas", precio=60, permitido_en_examen=False, activo=True)
    c2 = Comodin(clave=TipoComodin.abogado, nombre="Abogado Senior", descripcion="Ver nota", precio=90, permitido_en_examen=False, activo=True)
    c3 = Comodin(clave=TipoComodin.amparo, nombre="Amparo", descripcion="Evita perder vida", precio=120, permitido_en_examen=False, activo=True)

    with patch.object(TiendaServicio, "listar_catalogo", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [
            {"clave": "lupa", "nombre": "Lupa de Auditor", "descripcion": "Ver trampas", "precio": 60, "permitido_en_examen": False},
            {"clave": "abogado", "nombre": "Abogado Senior", "descripcion": "Ver nota", "precio": 90, "permitido_en_examen": False},
            {"clave": "amparo", "nombre": "Amparo", "descripcion": "Evita perder vida", "precio": 120, "permitido_en_examen": False},
        ]
        resp = client.get("/v1/tienda")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["clave"] == "lupa"
        assert data[0]["precio"] == 60


def test_comprar_comodin_exito():
    usuario = _crear_usuario(monedas=150)
    comodin = Comodin(clave=TipoComodin.lupa, nombre="Lupa", descripcion="Lupa", precio=60, permitido_en_examen=False, activo=True)

    sesion_mock = AsyncMock()
    servicio = TiendaServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_comodin_por_clave = AsyncMock(return_value=comodin)
    servicio._repo.crear_movimiento_economia = AsyncMock()

    with patch("app.dominios.tienda.router.TiendaServicio", return_value=servicio):
        resp = client.post("/v1/tienda/compras", json={"comodin": "lupa", "cantidad": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["monedas"] == 30
        assert data["inventario"]["lupa"] == 3
        servicio._repo.crear_movimiento_economia.assert_awaited_once()


def test_comprar_comodin_saldo_insuficiente():
    usuario = _crear_usuario(monedas=50)
    comodin = Comodin(clave=TipoComodin.lupa, nombre="Lupa", descripcion="Lupa", precio=60, permitido_en_examen=False, activo=True)

    sesion_mock = AsyncMock()
    servicio = TiendaServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_comodin_por_clave = AsyncMock(return_value=comodin)

    with patch("app.dominios.tienda.router.TiendaServicio", return_value=servicio):
        resp = client.post("/v1/tienda/compras", json={"comodin": "lupa", "cantidad": 1})
        assert resp.status_code == 409
        data = resp.json()
        assert data["error"]["codigo"] == "SALDO_INSUFICIENTE"


def test_comprar_comodin_no_encontrado():
    usuario = _crear_usuario(monedas=500)

    sesion_mock = AsyncMock()
    servicio = TiendaServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_comodin_por_clave = AsyncMock(return_value=None)

    with patch("app.dominios.tienda.router.TiendaServicio", return_value=servicio):
        resp = client.post("/v1/tienda/compras", json={"comodin": "congelar_racha", "cantidad": 1})
        assert resp.status_code == 404
        assert resp.json()["error"]["codigo"] == "NO_ENCONTRADO"


@pytest.mark.asyncio
async def test_compras_simultaneas_saldo_justo():
    usuario = _crear_usuario(monedas=60, inventario={"lupa": 0, "abogado": 0, "amparo": 0, "congelar_racha": 0})
    comodin = Comodin(clave=TipoComodin.lupa, nombre="Lupa", descripcion="Lupa", precio=60, permitido_en_examen=False, activo=True)

    sesion_mock = AsyncMock()
    servicio = TiendaServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_comodin_por_clave = AsyncMock(return_value=comodin)
    servicio._repo.crear_movimiento_economia = AsyncMock()

    datos = ComprarComodinInput(comodin="lupa", cantidad=1)
    res1 = await servicio.comprar_comodin(USUARIO_ID_TEST, datos)
    assert res1.monedas == 0
    assert res1.inventario.lupa == 1

    with pytest.raises(SaldoInsuficiente):
        await servicio.comprar_comodin(USUARIO_ID_TEST, datos)


def test_usar_comodin_amparo():
    usuario = _crear_usuario(inventario={"lupa": 1, "abogado": 1, "amparo": 1, "congelar_racha": 0}, amparo_activo=False)
    intento = Intento(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        sprint_id=1,
        tipo=TipoIntento.sprint,
        estado=EstadoIntento.en_curso,
        tarjetas_asignadas=[],
    )

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id_con_lock = AsyncMock(return_value=intento)

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post(f"/v1/intentos/{intento.id}/comodines", json={"comodin": "amparo"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["comodin"] == "amparo"
        assert data["amparo_activo"] is True
        assert data["inventario"]["amparo"] == 0
        assert usuario.amparo_activo is True


def test_usar_comodin_amparo_ya_activo():
    usuario = _crear_usuario(inventario={"lupa": 1, "abogado": 1, "amparo": 1, "congelar_racha": 0}, amparo_activo=True)
    intento = Intento(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        sprint_id=1,
        tipo=TipoIntento.sprint,
        estado=EstadoIntento.en_curso,
        tarjetas_asignadas=[],
    )

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id_con_lock = AsyncMock(return_value=intento)

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post(f"/v1/intentos/{intento.id}/comodines", json={"comodin": "amparo"})
        assert resp.status_code == 409
        assert resp.json()["error"]["codigo"] == "COMODIN_YA_USADO"


def test_usar_comodin_lupa():
    tid = uuid.uuid4()
    usuario = _crear_usuario(inventario={"lupa": 2, "abogado": 1, "amparo": 1, "congelar_racha": 0})
    intento = Intento(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        sprint_id=1,
        tipo=TipoIntento.sprint,
        estado=EstadoIntento.en_curso,
        tarjetas_asignadas=[{"orden": 1, "tarjeta_id": str(tid), "version": 1, "comodines": []}],
    )
    tarjeta = Tarjeta(
        id=tid,
        version=1,
        sprint_id=1,
        tipo=TipoTarjeta.normal,
        categoria="datos",
        personaje_nombre="Dev",
        personaje_rol="Frontend",
        iniciales="DEV",
        texto="Texto",
        explicacion="Exp",
        array_palabras_trampa=["trampa1", "trampa2"],
        nota_abogado="Nota",
        contenido_interactivo={"veredictos": {}},
        activa=True,
    )

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id_con_lock = AsyncMock(return_value=intento)
    servicio._repo.buscar_tarjeta_version = AsyncMock(return_value=tarjeta)

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post(f"/v1/intentos/{intento.id}/comodines", json={"comodin": "lupa", "tarjeta_orden": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["comodin"] == "lupa"
        assert "trampa1" in data["efecto"]["palabras_trampa"]
        assert data["inventario"]["lupa"] == 1
        assert "lupa" in intento.tarjetas_asignadas[0]["comodines"]


def test_usar_comodin_abogado():
    tid = uuid.uuid4()
    usuario = _crear_usuario(inventario={"lupa": 1, "abogado": 1, "amparo": 1, "congelar_racha": 0})
    intento = Intento(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        sprint_id=1,
        tipo=TipoIntento.sprint,
        estado=EstadoIntento.en_curso,
        tarjetas_asignadas=[{"orden": 2, "tarjeta_id": str(tid), "version": 1, "comodines": []}],
    )
    tarjeta = Tarjeta(
        id=tid,
        version=1,
        sprint_id=1,
        tipo=TipoTarjeta.normal,
        categoria="datos",
        personaje_nombre="Dev",
        personaje_rol="Frontend",
        iniciales="DEV",
        texto="Texto",
        explicacion="Exp",
        nota_abogado="Articulo 16 constitucional",
        contenido_interactivo={"veredictos": {}},
        activa=True,
    )

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id_con_lock = AsyncMock(return_value=intento)
    servicio._repo.buscar_tarjeta_version = AsyncMock(return_value=tarjeta)

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post(f"/v1/intentos/{intento.id}/comodines", json={"comodin": "abogado", "tarjeta_orden": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["comodin"] == "abogado"
        assert data["efecto"]["nota_abogado"] == "Articulo 16 constitucional"
        assert data["inventario"]["abogado"] == 0


def test_usar_comodin_repetido_en_tarjeta():
    tid = uuid.uuid4()
    usuario = _crear_usuario(inventario={"lupa": 2, "abogado": 1, "amparo": 1, "congelar_racha": 0})
    intento = Intento(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        sprint_id=1,
        tipo=TipoIntento.sprint,
        estado=EstadoIntento.en_curso,
        tarjetas_asignadas=[{"orden": 1, "tarjeta_id": str(tid), "version": 1, "comodines": ["lupa"]}],
    )

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id_con_lock = AsyncMock(return_value=intento)

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post(f"/v1/intentos/{intento.id}/comodines", json={"comodin": "lupa", "tarjeta_orden": 1})
        assert resp.status_code == 409
        assert resp.json()["error"]["codigo"] == "COMODIN_YA_USADO"


def test_usar_comodin_en_examen():
    usuario = _crear_usuario(inventario={"lupa": 2, "abogado": 1, "amparo": 1, "congelar_racha": 0})
    intento = Intento(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        sprint_id=1,
        tipo=TipoIntento.examen,
        estado=EstadoIntento.en_curso,
        tarjetas_asignadas=[],
    )

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id_con_lock = AsyncMock(return_value=intento)

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post(f"/v1/intentos/{intento.id}/comodines", json={"comodin": "amparo"})
        assert resp.status_code == 403
        assert resp.json()["error"]["codigo"] == "SIN_PERMISO"


def test_usar_comodin_sin_inventario():
    usuario = _crear_usuario(inventario={"lupa": 0, "abogado": 0, "amparo": 0, "congelar_racha": 0})
    intento = Intento(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        sprint_id=1,
        tipo=TipoIntento.sprint,
        estado=EstadoIntento.en_curso,
        tarjetas_asignadas=[],
    )

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id_con_lock = AsyncMock(return_value=intento)

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post(f"/v1/intentos/{intento.id}/comodines", json={"comodin": "amparo"})
        assert resp.status_code == 409
        assert resp.json()["error"]["codigo"] == "SALDO_INSUFICIENTE"


def test_actualizar_racha_logro_7():
    ahora = datetime(2026, 11, 21, 12, 0, 0, tzinfo=ZoneInfo("America/Mexico_City"))
    ayer = (ahora - timedelta(days=1)).date()
    usuario = _crear_usuario(racha_actual=6, ultimo_dia_racha=ayer)

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)

    alcanzo_7 = servicio._actualizar_racha(usuario, ahora)
    assert alcanzo_7 is True
    assert usuario.racha_actual == 7
    assert usuario.racha_maxima == 7
    assert usuario.ultimo_dia_racha == ahora.date()
