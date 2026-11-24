from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.deps import usuario_actual
from app.core.errores import IntentoEnCurso, SaldoInsuficiente, YaRespondida
from app.core.reloj import now
from app.dominios.juego.servicio import JuegoServicio
from app.dominios.sync.servicio import SyncServicio
from app.dominios.tienda.servicio import TiendaServicio
from app.esquemas.juego import EnviarRespuestaInput, IniciarSprintInput
from app.esquemas.sync import ElementoSyncInput, SyncRespuestasInput
from app.esquemas.tienda import ComprarComodinInput
from app.main import app
from app.modelos.contenido import Sprint, Tarjeta
from app.modelos.economia import Comodin
from app.modelos.enums import (
    EstadoCuenta,
    EstadoIntento,
    EstadoProgreso,
    PerfilUsuario,
    ResultadoRespuesta,
    RolUsuario,
    TipoComodin,
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


def _crear_usuario(monedas: int = 60) -> Usuario:
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
        amparo_activo=False,
        racha_actual=0,
        racha_maxima=0,
        ultimo_dia_racha=None,
        zona_horaria="America/Mexico_City",
        preferencias={},
        inventario={"lupa": 0, "abogado": 0, "amparo": 0, "congelar_racha": 0},
        reto_diario={},
        estado_cuenta=EstadoCuenta.activo,
    )


@pytest.mark.asyncio
async def test_dos_compras_simultaneas_saldo_justo_solo_una_aplica():
    usuario = _crear_usuario(monedas=60)
    comodin = Comodin(
        clave=TipoComodin.lupa,
        nombre="Lupa",
        descripcion="Lupa",
        precio=60,
        permitido_en_examen=False,
        activo=True,
    )

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


@pytest.mark.asyncio
async def test_dos_intentos_sprint_simultaneos_solo_uno_crea():
    usuario = _crear_usuario()
    sprint = Sprint(
        id=1,
        modulo_id=1,
        orden=1,
        titulo="Sprint 1",
        objetivo="Obj",
        es_examen=False,
        ini_presupuesto=70,
        ini_reputacion=60,
        ini_velocidad=50,
        ini_riesgo=25,
        monedas_max=60,
    )
    progreso = ProgresoSprint(
        usuario_id=USUARIO_ID_TEST,
        sprint_id=1,
        estado=EstadoProgreso.disponible,
        estrellas=0,
        mejor_aciertos=0,
        perfecto=False,
    )

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)

    intento_en_curso = None

    async def mock_buscar_intento_en_curso(uid):
        return intento_en_curso

    async def mock_crear_intento(it):
        nonlocal intento_en_curso
        intento_en_curso = it
        return it

    tarjetas = [
        Tarjeta(
            id=uuid.uuid4(),
            version=1,
            sprint_id=1,
            tipo=TipoTarjeta.normal
            if i <= 6
            else (TipoTarjeta.evidencia if i <= 9 else TipoTarjeta.justificacion),
            categoria="datos",
            personaje_nombre="Dev",
            personaje_rol="Frontend",
            iniciales="DEV",
            texto="Texto",
            explicacion="Exp",
            contenido_interactivo={
                "veredictos": {
                    "legal": {"resultado": "correcto"},
                    "ilegal": {"resultado": "incorrecto"},
                    "condicional": {"resultado": "parcial"},
                    "escalar": {"resultado": "incorrecto"},
                },
                "evidencia": {
                    "formato": "codigo",
                    "nombre_archivo": "a.py",
                    "contenido_texto": "x",
                    "lineas_infractoras": [1],
                }
                if i in (7, 8, 9)
                else None,
                "micro_pregunta": {
                    "tipo": "por_que",
                    "enunciado": "?",
                    "opciones": [
                        {"id": 1, "texto": "A", "es_correcta": True},
                        {"id": 2, "texto": "B", "es_correcta": False},
                    ],
                },
            },
            activa=True,
        )
        for i in range(1, 11)
    ]

    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_intento_por_id = AsyncMock(return_value=None)
    servicio._repo.buscar_sprint = AsyncMock(return_value=sprint)
    servicio._repo.buscar_progreso = AsyncMock(return_value=progreso)
    servicio._repo.buscar_intento_en_curso = AsyncMock(side_effect=mock_buscar_intento_en_curso)
    servicio._repo.buscar_tarjetas_activas_sprint = AsyncMock(return_value=tarjetas)
    servicio._repo.obtener_tarjetas_ultimos_intentos = AsyncMock(return_value=set())
    servicio._repo.crear_intento = AsyncMock(side_effect=mock_crear_intento)

    res1 = await servicio.iniciar_sprint(USUARIO_ID_TEST, 1, IniciarSprintInput(id=uuid.uuid4()))
    assert res1.intento_id is not None

    with pytest.raises(IntentoEnCurso):
        await servicio.iniciar_sprint(USUARIO_ID_TEST, 1, IniciarSprintInput(id=uuid.uuid4()))


@pytest.mark.asyncio
async def test_dos_respuestas_simultaneas_misma_tarjeta_rechaza_segunda():
    tid = uuid.uuid4()
    intento_id = uuid.uuid4()
    usuario = _crear_usuario()
    intento = Intento(
        id=intento_id,
        usuario_id=USUARIO_ID_TEST,
        sprint_id=1,
        tipo=TipoIntento.sprint,
        estado=EstadoIntento.en_curso,
        ind_presupuesto=70,
        ind_reputacion=60,
        ind_velocidad=50,
        ind_riesgo=25,
        aciertos=0,
        parciales=0,
        errores=0,
        xp_ganada=0,
        monedas_ganadas=0,
        tarjetas_asignadas=[{"orden": 1, "tarjeta_id": str(tid), "version": 1}],
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
        contenido_interactivo={"veredictos": {"legal": {"resultado": "correcto"}}},
        activa=True,
    )
    sprint = Sprint(
        id=1,
        modulo_id=1,
        orden=1,
        titulo="S1",
        objetivo="Obj",
        es_examen=False,
        ini_presupuesto=70,
        ini_reputacion=60,
        ini_velocidad=50,
        ini_riesgo=25,
        monedas_max=60,
    )

    sesion_mock = AsyncMock()
    servicio = JuegoServicio(sesion_mock)

    respuesta_guardada = None

    async def mock_buscar_resp(iid, card_id):
        return respuesta_guardada

    async def mock_crear_resp(resp):
        nonlocal respuesta_guardada
        respuesta_guardada = resp
        return resp

    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)
    servicio._repo.buscar_respuesta_por_id = AsyncMock(return_value=None)
    servicio._repo.buscar_intento_por_id_con_lock = AsyncMock(return_value=intento)
    servicio._repo.buscar_respuesta_por_tarjeta = AsyncMock(side_effect=mock_buscar_resp)
    servicio._repo.buscar_tarjeta_version = AsyncMock(return_value=tarjeta)
    servicio._repo.buscar_sprint = AsyncMock(return_value=sprint)
    servicio._repo.crear_respuesta = AsyncMock(side_effect=mock_crear_resp)
    servicio._repo.listar_respuestas_intento = AsyncMock(return_value=[])
    servicio._repo.contar_respuestas_intento = AsyncMock(return_value=1)

    datos1 = EnviarRespuestaInput(id=uuid.uuid4(), tarjeta_id=tid, veredicto="legal", segundos=5.0)
    res1 = await servicio.enviar_respuesta(USUARIO_ID_TEST, intento_id, datos1)
    assert res1.resultado == "correcto"

    datos2 = EnviarRespuestaInput(id=uuid.uuid4(), tarjeta_id=tid, veredicto="legal", segundos=5.0)
    with pytest.raises(YaRespondida):
        await servicio.enviar_respuesta(USUARIO_ID_TEST, intento_id, datos2)


@pytest.mark.asyncio
async def test_sync_lote_repetido_devuelve_duplicada():
    usuario = _crear_usuario()
    intento_id = uuid.uuid4()
    resp_id = uuid.uuid4()

    sesion_mock = AsyncMock()
    servicio = SyncServicio(sesion_mock)
    servicio._repo.buscar_usuario_con_lock = AsyncMock(return_value=usuario)

    resp_existente = None

    async def mock_buscar_resp(rid):
        return resp_existente

    servicio._repo.buscar_respuesta_por_id = AsyncMock(side_effect=mock_buscar_resp)

    intento = Intento(
        id=intento_id,
        usuario_id=USUARIO_ID_TEST,
        sprint_id=1,
        tipo=TipoIntento.sprint,
        estado=EstadoIntento.en_curso,
        ind_presupuesto=70,
        ind_reputacion=60,
        ind_velocidad=50,
        ind_riesgo=25,
        aciertos=0,
        parciales=0,
        errores=0,
        xp_ganada=0,
        monedas_ganadas=0,
        tarjetas_asignadas=[{"orden": 1, "tarjeta_id": str(uuid.uuid4()), "version": 1}],
    )
    servicio._repo.buscar_intento_por_id = AsyncMock(return_value=intento)

    with patch("app.dominios.sync.servicio.JuegoServicio.enviar_respuesta") as mock_envio:
        mock_envio.return_value = AsyncMock(
            resultado="correcto",
            estado_intento="en_curso",
            indicadores={"presupuesto": 70, "reputacion": 60, "velocidad": 50, "riesgo_legal": 25},
            cierre=None,
        )

        lote = SyncRespuestasInput(
            respuestas=[
                ElementoSyncInput(
                    id=resp_id,
                    intento_id=intento_id,
                    tarjeta_id=uuid.uuid4(),
                    veredicto="legal",
                    segundos=3.0,
                )
            ]
        )

        res1 = await servicio.sincronizar(USUARIO_ID_TEST, lote)
        assert res1.resultados[0].estado == "aplicada"

        resp_existente = Respuesta(
            id=resp_id,
            intento_id=intento_id,
            tarjeta_id=uuid.uuid4(),
            resultado=ResultadoRespuesta.correcto,
        )

        res2 = await servicio.sincronizar(USUARIO_ID_TEST, lote)
        assert res2.resultados[0].estado == "duplicada"
