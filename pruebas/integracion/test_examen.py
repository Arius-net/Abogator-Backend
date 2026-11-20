from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.core.deps import usuario_actual
from app.core.reloj import now
from app.dominios.juego.servicio import JuegoServicio
from app.esquemas.examen import IniciarExamenInput
from app.main import app
from app.modelos.contenido import Modulo, Sprint, Tarjeta
from app.modelos.enums import (
    EstadoCuenta,
    EstadoIntento,
    EstadoProgreso,
    PerfilUsuario,
    ResultadoRespuesta,
    RolUsuario,
    TipoIntento,
    TipoTarjeta,
)
from app.modelos.juego import Intento, ProgresoSprint, Respuesta
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


def _crear_usuario(vidas: int = 5, tiempo_extendido: bool = False) -> Usuario:
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
        preferencias={"tiempo_extendido": tiempo_extendido},
        inventario={"lupa": 0, "abogado": 0, "amparo": 0, "congelar_racha": 0},
        reto_diario={},
        estado_cuenta=EstadoCuenta.activo,
    )


def _crear_escenario_mock() -> dict:
    decisiones = []
    for i in range(1, 11):
        hc = 0 if i <= 3 else (6 if i <= 6 else (24 if i <= 8 else 72))
        decisiones.append({
            "orden": i,
            "tarjeta_id": str(uuid.uuid4()),
            "hora_crisis": hc,
            "replica_jefe": f"Replica {i}",
            "fundamentos": [
                {"id": 1, "texto": "Fundamento Correcto", "es_correcta": True},
                {"id": 2, "texto": "Fundamento Incorrecto", "es_correcta": False},
            ],
        })
    return {
        "nombre_jefe": "Inspectora Vega",
        "titulo_crisis": "Brecha de Datos",
        "descripcion": "Crisis grave",
        "hp_inicial": 100,
        "dano_por_golpe": 20,
        "segundos_decision": 15,
        "segundos_contraargumento": 8,
        "decisiones": decisiones,
    }


def _crear_tarjeta_examen(tid: uuid.UUID) -> Tarjeta:
    return Tarjeta(
        id=tid,
        version=1,
        sprint_id=6,
        tipo=TipoTarjeta.normal,
        categoria="datos",
        personaje_nombre="Inspectora",
        personaje_rol="Jefa",
        iniciales="VEG",
        texto="Texto Decision",
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


def test_iniciar_examen_exito():
    escenario = _crear_escenario_mock()
    sprint = Sprint(id=6, modulo_id=1, orden=6, titulo="Examen Final", objetivo="Objetivo", es_examen=True, escenario_jefe=escenario, ini_presupuesto=70, ini_reputacion=60, ini_velocidad=50, ini_riesgo=25, monedas_max=60)
    usuario = _crear_usuario()

    tid_primero = uuid.UUID(escenario["decisiones"][0]["tarjeta_id"])
    tarjeta_1 = _crear_tarjeta_examen(tid_primero)

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id = AsyncMock(return_value=None)
    servicio._repo.buscar_sprint = AsyncMock(return_value=sprint)
    servicio._repo.contar_sprints_completados_modulo = AsyncMock(return_value=5)
    servicio._repo.buscar_certificado = AsyncMock(return_value=None)
    servicio._repo.buscar_intento_en_curso = AsyncMock(return_value=None)
    servicio._repo.crear_intento = AsyncMock()
    servicio._repo.buscar_tarjeta_version = AsyncMock(return_value=tarjeta_1)

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post("/v1/examenes/6/intentos", json={})
        assert resp.status_code == 201
        data = resp.json()
        assert data["hp_jefe"] == 100
        assert data["titulo_crisis"] == "Brecha de Datos"
        assert data["decision"]["orden"] == 1


def test_iniciar_examen_sprints_incompletos_retorna_403():
    escenario = _crear_escenario_mock()
    sprint = Sprint(id=6, modulo_id=1, orden=6, titulo="Examen", objetivo="Objetivo", es_examen=True, escenario_jefe=escenario, ini_presupuesto=70, ini_reputacion=60, ini_velocidad=50, ini_riesgo=25, monedas_max=60)
    usuario = _crear_usuario()

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id = AsyncMock(return_value=None)
    servicio._repo.buscar_sprint = AsyncMock(return_value=sprint)
    servicio._repo.contar_sprints_completados_modulo = AsyncMock(return_value=4)

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post("/v1/examenes/6/intentos", json={})
        assert resp.status_code == 403
        assert resp.json()["error"]["codigo"] == "SPRINT_BLOQUEADO"


def test_responder_decision_examen_tiempo_agotado():
    ahora = now()
    tid = uuid.uuid4()
    usuario = _crear_usuario(vidas=5)
    escenario = _crear_escenario_mock()
    sprint = Sprint(id=6, modulo_id=1, orden=6, titulo="Examen", objetivo="Objetivo", es_examen=True, escenario_jefe=escenario, ini_presupuesto=70, ini_reputacion=60, ini_velocidad=50, ini_riesgo=25, monedas_max=60)

    entregada_hace_30s = ahora - timedelta(seconds=30)
    intento = Intento(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        sprint_id=6,
        tipo=TipoIntento.examen,
        estado=EstadoIntento.en_curso,
        ind_presupuesto=70,
        ind_reputacion=60,
        ind_velocidad=50,
        ind_riesgo=25,
        hp_jefe=100,
        tarjetas_asignadas=[
            {"orden": 1, "tarjeta_id": str(tid), "version": 1, "entregada_en": entregada_hace_30s.isoformat(), "pausa_s": 0},
            {"orden": 2, "tarjeta_id": str(uuid.uuid4()), "version": 1, "entregada_en": None, "pausa_s": 0},
        ],
    )
    tarjeta = _crear_tarjeta_examen(tid)

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id_con_lock = AsyncMock(return_value=intento)
    servicio._repo.buscar_respuesta_por_id = AsyncMock(return_value=None)
    servicio._repo.buscar_respuesta_por_tarjeta = AsyncMock(return_value=None)
    servicio._repo.buscar_tarjeta_version = AsyncMock(return_value=tarjeta)
    servicio._repo.buscar_sprint = AsyncMock(return_value=sprint)
    servicio._repo.listar_respuestas_intento = AsyncMock(return_value=[])
    servicio._repo.crear_movimiento_economia = AsyncMock()
    servicio._repo.crear_respuesta = AsyncMock()

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post(
            f"/v1/intentos/{intento.id}/respuestas",
            json={"tarjeta_id": str(tid), "veredicto": "legal", "segundos": 30.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resultado"] == "tiempo_agotado"
        assert usuario.vidas == 4
        assert intento.errores == 1
        assert data["siguiente_orden"] == 2


def test_contraargumento_acierto_reduce_hp():
    ahora = now()
    tid = uuid.uuid4()
    rid = uuid.uuid4()
    usuario = _crear_usuario(vidas=5)
    escenario = _crear_escenario_mock()
    sprint = Sprint(id=6, modulo_id=1, orden=6, titulo="Examen", objetivo="Objetivo", es_examen=True, escenario_jefe=escenario, ini_presupuesto=70, ini_reputacion=60, ini_velocidad=50, ini_riesgo=25, monedas_max=60)

    intento = Intento(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        sprint_id=6,
        tipo=TipoIntento.examen,
        estado=EstadoIntento.en_curso,
        hp_jefe=100,
        tarjetas_asignadas=[
            {
                "orden": 1,
                "tarjeta_id": str(tid),
                "version": 1,
                "contra_entregada_en": ahora.isoformat(),
                "fundamentos": [
                    {"id": 1, "texto": "Articulo correcto", "es_correcta": True},
                    {"id": 2, "texto": "Falso", "es_correcta": False},
                ],
            },
            {
                "orden": 2,
                "tarjeta_id": str(uuid.uuid4()),
                "version": 1,
                "hora_crisis": 0,
            },
        ],
    )
    resp_obj = Respuesta(
        id=rid,
        intento_id=intento.id,
        tarjeta_id=tid,
        resultado=ResultadoRespuesta.correcto,
        contraargumento_ok=None,
    )
    tarjeta_2 = _crear_tarjeta_examen(uuid.UUID(intento.tarjetas_asignadas[1]["tarjeta_id"]))

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id_con_lock = AsyncMock(return_value=intento)
    servicio._repo.buscar_respuesta_por_id = AsyncMock(return_value=resp_obj)
    servicio._repo.buscar_sprint = AsyncMock(return_value=sprint)
    servicio._repo.buscar_tarjeta_version = AsyncMock(return_value=tarjeta_2)

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post(
            f"/v1/intentos/{intento.id}/contraargumento",
            json={"respuesta_id": str(rid), "fundamento_id": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["contraargumento_ok"] is True
        assert data["hp_jefe"] == 80
        assert data["siguiente_decision"]["orden"] == 2


def test_contraargumento_derrota_jefe_emite_certificado_y_folio():
    ahora = now()
    tid = uuid.uuid4()
    rid = uuid.uuid4()
    usuario = _crear_usuario(vidas=5)
    escenario = _crear_escenario_mock()
    escenario["dano_por_golpe"] = 100
    modulo = Modulo(id=1, numero=1, titulo="Mod 1", etapa_startup="Semilla", color_token="blue", activo=True)
    sprint = Sprint(id=6, modulo_id=1, orden=6, titulo="Examen", objetivo="Objetivo", es_examen=True, escenario_jefe=escenario, ini_presupuesto=70, ini_reputacion=60, ini_velocidad=50, ini_riesgo=25, monedas_max=60)

    intento = Intento(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        sprint_id=6,
        tipo=TipoIntento.examen,
        estado=EstadoIntento.en_curso,
        hp_jefe=100,
        xp_ganada=50,
        monedas_ganadas=25,
        tarjetas_asignadas=[
            {
                "orden": 1,
                "tarjeta_id": str(tid),
                "version": 1,
                "contra_entregada_en": ahora.isoformat(),
                "fundamentos": [{"id": 1, "texto": "Correcto", "es_correcta": True}],
            }
        ],
    )
    resp_obj = Respuesta(
        id=rid,
        intento_id=intento.id,
        tarjeta_id=tid,
        resultado=ResultadoRespuesta.correcto,
        contraargumento_ok=None,
    )

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id_con_lock = AsyncMock(return_value=intento)
    servicio._repo.buscar_respuesta_por_id = AsyncMock(return_value=resp_obj)
    servicio._repo.buscar_sprint = AsyncMock(return_value=sprint)
    servicio._repo.buscar_modulo = AsyncMock(return_value=modulo)
    servicio._repo.obtener_siguiente_folio_seq = AsyncMock(return_value=42)
    servicio._repo.crear_certificado = AsyncMock()
    servicio._repo.buscar_progreso = AsyncMock(return_value=ProgresoSprint(usuario_id=USUARIO_ID_TEST, sprint_id=6, estado=EstadoProgreso.disponible, estrellas=0, mejor_aciertos=0, perfecto=False))
    servicio._repo.desbloquear_siguiente_modulo = AsyncMock()
    servicio._repo.otorgar_insignia = AsyncMock(return_value=True)
    servicio._repo.crear_movimiento_economia = AsyncMock()

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post(
            f"/v1/intentos/{intento.id}/contraargumento",
            json={"respuesta_id": str(rid), "fundamento_id": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["hp_jefe"] == 0
        assert data["cierre"]["estado"] == "completado"
        assert "modulo_aprobado" in data["cierre"]["insignias_nuevas"]
        servicio._repo.crear_certificado.assert_awaited_once()
        cert_creado = servicio._repo.crear_certificado.call_args[0][0]
        assert cert_creado.folio == f"AG-{ahora.year}-1-000042"


def test_pausa_sin_tiempo_extendido_falla():
    usuario = _crear_usuario(tiempo_extendido=False)
    intento = Intento(id=uuid.uuid4(), usuario_id=USUARIO_ID_TEST, sprint_id=6, tipo=TipoIntento.examen, estado=EstadoIntento.en_curso)

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post(f"/v1/intentos/{intento.id}/pausa")
        assert resp.status_code == 403
        assert resp.json()["error"]["codigo"] == "PAUSA_NO_PERMITIDA"


def test_pausa_y_reanudar_exitoso():
    ahora = now()
    tid = uuid.uuid4()
    usuario = _crear_usuario(tiempo_extendido=True)
    escenario = _crear_escenario_mock()
    sprint = Sprint(id=6, modulo_id=1, orden=6, titulo="Examen", objetivo="Objetivo", es_examen=True, escenario_jefe=escenario, ini_presupuesto=70, ini_reputacion=60, ini_velocidad=50, ini_riesgo=25, monedas_max=60)
    intento = Intento(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        sprint_id=6,
        tipo=TipoIntento.examen,
        estado=EstadoIntento.en_curso,
        pausado_en=None,
        pausa_acumulada_s=0,
        tarjetas_asignadas=[{"orden": 1, "tarjeta_id": str(tid), "version": 1, "entregada_en": ahora.isoformat(), "pausa_s": 0}],
    )
    tarjeta = _crear_tarjeta_examen(tid)

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id_con_lock = AsyncMock(return_value=intento)
    servicio._repo.buscar_sprint = AsyncMock(return_value=sprint)
    servicio._repo.buscar_tarjeta_version = AsyncMock(return_value=tarjeta)
    servicio._repo.buscar_respuesta_por_tarjeta = AsyncMock(return_value=None)

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp_pausa = client.post(f"/v1/intentos/{intento.id}/pausa")
        assert resp_pausa.status_code == 200
        assert resp_pausa.json()["pausado"] is True

        resp_reanudar = client.post(f"/v1/intentos/{intento.id}/reanudar")
        assert resp_reanudar.status_code == 200
        data_reanudar = resp_reanudar.json()
        assert data_reanudar["pausado"] is False
        assert data_reanudar["segundos_restantes"] > 0


def test_reanudar_pausa_excedida_cierra_abandonado():
    ahora = now()
    usuario = _crear_usuario(tiempo_extendido=True)
    intento = Intento(
        id=uuid.uuid4(),
        usuario_id=USUARIO_ID_TEST,
        sprint_id=6,
        tipo=TipoIntento.examen,
        estado=EstadoIntento.en_curso,
        pausado_en=ahora - timedelta(seconds=650),
        pausa_acumulada_s=0,
    )

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id_con_lock = AsyncMock(return_value=intento)

    with patch("app.dominios.juego.router.JuegoServicio", return_value=servicio):
        resp = client.post(f"/v1/intentos/{intento.id}/reanudar")
        assert resp.status_code == 409
        assert resp.json()["error"]["codigo"] == "PAUSA_AGOTADA"
        assert intento.estado == EstadoIntento.abandonado
