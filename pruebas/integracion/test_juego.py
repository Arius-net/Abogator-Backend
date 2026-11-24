from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.deps import usuario_actual
from app.core.errores import (
    IntentoCerrado,
    IntentoEnCurso,
    NoEncontrado,
    PeticionInvalida,
    SinVidas,
    SprintBloqueado,
    YaRespondida,
)
from app.core.reloj import now
from app.dominios.juego.servicio import JuegoServicio
from app.esquemas.juego import (
    AbandonarRespuesta,
    CierreIntentoRespuesta,
    EstadoIntentoRespuesta,
    PaqueteSprintRespuesta,
    PaqueteTarjeta,
    RecompensaRespuesta,
    RespuestaEnvioRespuesta,
)
from app.main import app
from app.modelos.contenido import Sprint, Tarjeta
from app.modelos.enums import (
    EstadoCuenta,
    EstadoIntento,
    EstadoProgreso,
    PerfilUsuario,
    ResultadoRespuesta,
    RolUsuario,
    TipoIntento,
    TipoTarjeta,
    Veredicto,
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


def _crear_paquete_mock(intento_id: uuid.UUID) -> PaqueteSprintRespuesta:
    return PaqueteSprintRespuesta(
        intento_id=intento_id,
        clave_intento="clave_b64_test",
        vidas=5,
        indicadores={"presupuesto": 70, "reputacion": 60, "velocidad": 50, "riesgo_legal": 25},
        tarjetas=[
            PaqueteTarjeta(
                orden=1,
                tarjeta_id=uuid.uuid4(),
                version=1,
                tipo="normal",
                categoria="datos",
                personaje_nombre="Dev",
                personaje_rol="Frontend",
                iniciales="DEV",
                texto="Texto 1",
                evidencia=None,
                micro_pregunta={
                    "tipo": "por_que",
                    "enunciado": "¿Por qué?",
                    "opciones": [{"id": 1, "texto": "A"}],
                },
                resolucion_cifrada="blob_cifrado",
            )
        ],
    )


def _crear_respuesta_envio_mock(
    cierre: CierreIntentoRespuesta | None = None,
) -> RespuestaEnvioRespuesta:
    return RespuestaEnvioRespuesta(
        resultado="correcto",
        veredicto_correcto="ilegal",
        explicacion="Explicación legal.",
        impacto={"presupuesto": -5, "reputacion": 5, "velocidad": -10, "riesgo_legal": -20},
        indicadores={"presupuesto": 65, "reputacion": 65, "velocidad": 40, "riesgo_legal": 5},
        recompensa=RecompensaRespuesta(xp=15, monedas=5, bonos=["por_que"]),
        vidas=5,
        amparo_usado=False,
        estado_intento="completado" if cierre else "en_curso",
        siguiente_orden=None if cierre else 2,
        cierre=cierre,
    )


class TestEndpointsJuego:
    def test_iniciar_sprint_exitoso(self) -> None:
        intento_id = uuid.uuid4()
        paquete_mock = _crear_paquete_mock(intento_id)
        with patch.object(JuegoServicio, "iniciar_sprint", new_callable=AsyncMock) as m_ini:
            m_ini.return_value = paquete_mock
            resp = client.post(
                "/v1/sprints/1/intentos",
                json={"id": str(intento_id)},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["intento_id"] == str(intento_id)
        assert data["vidas"] == 5
        assert len(data["tarjetas"]) == 1

    def test_iniciar_sprint_sin_vidas_retorna_403(self) -> None:
        with patch.object(JuegoServicio, "iniciar_sprint", new_callable=AsyncMock) as m_ini:
            m_ini.side_effect = SinVidas(detalle={"proxima_vida_en": "2026-11-21T14:00:00Z"})
            resp = client.post("/v1/sprints/1/intentos", json={})

        assert resp.status_code == 403
        assert resp.json()["error"]["codigo"] == "SIN_VIDAS"

    def test_iniciar_sprint_bloqueado_retorna_403(self) -> None:
        with patch.object(JuegoServicio, "iniciar_sprint", new_callable=AsyncMock) as m_ini:
            m_ini.side_effect = SprintBloqueado()
            resp = client.post("/v1/sprints/2/intentos", json={})

        assert resp.status_code == 403
        assert resp.json()["error"]["codigo"] == "SPRINT_BLOQUEADO"

    def test_iniciar_sprint_intento_en_curso_retorna_409(self) -> None:
        otro_id = str(uuid.uuid4())
        with patch.object(JuegoServicio, "iniciar_sprint", new_callable=AsyncMock) as m_ini:
            m_ini.side_effect = IntentoEnCurso(detalle={"intento_id": otro_id})
            resp = client.post("/v1/sprints/1/intentos", json={})

        assert resp.status_code == 409
        assert resp.json()["error"]["codigo"] == "INTENTO_EN_CURSO"
        assert resp.json()["error"]["detalle"]["intento_id"] == otro_id

    def test_enviar_respuesta_exitosa(self) -> None:
        intento_id = uuid.uuid4()
        tarjeta_id = uuid.uuid4()
        resp_id = uuid.uuid4()
        mock_env = _crear_respuesta_envio_mock()

        with patch.object(JuegoServicio, "enviar_respuesta", new_callable=AsyncMock) as m_env:
            m_env.return_value = mock_env
            payload = {
                "id": str(resp_id),
                "tarjeta_id": str(tarjeta_id),
                "veredicto": "ilegal",
                "segundos": 4.5,
                "por_que_opcion_id": 1,
            }
            resp = client.post(f"/v1/intentos/{intento_id}/respuestas", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["resultado"] == "correcto"
        assert data["veredicto_correcto"] == "ilegal"
        assert data["recompensa"]["xp"] == 15

    def test_enviar_respuesta_incorrecta(self) -> None:
        intento_id = uuid.uuid4()
        tarjeta_id = uuid.uuid4()
        resp_id = uuid.uuid4()
        mock_env = _crear_respuesta_envio_mock()
        mock_env.resultado = "incorrecto"
        mock_env.veredicto_correcto = "ilegal"
        mock_env.recompensa.xp = 0
        mock_env.recompensa.monedas = 0

        with patch.object(JuegoServicio, "enviar_respuesta", new_callable=AsyncMock) as m_env:
            m_env.return_value = mock_env
            payload = {
                "id": str(resp_id),
                "tarjeta_id": str(tarjeta_id),
                "veredicto": "legal",
                "segundos": 4.5,
                "por_que_opcion_id": 1,
            }
            resp = client.post(f"/v1/intentos/{intento_id}/respuestas", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["resultado"] == "incorrecto"
        assert data["veredicto_correcto"] == "ilegal"

    def test_enviar_respuesta_ya_respondida_retorna_409(self) -> None:
        intento_id = uuid.uuid4()
        tarjeta_id = uuid.uuid4()
        with patch.object(JuegoServicio, "enviar_respuesta", new_callable=AsyncMock) as m_env:
            m_env.side_effect = YaRespondida()
            payload = {
                "id": str(uuid.uuid4()),
                "tarjeta_id": str(tarjeta_id),
                "veredicto": "legal",
                "segundos": 3.0,
            }
            resp = client.post(f"/v1/intentos/{intento_id}/respuestas", json=payload)

        assert resp.status_code == 409
        assert resp.json()["error"]["codigo"] == "YA_RESPONDIDA"

    def test_obtener_intento(self) -> None:
        intento_id = uuid.uuid4()
        mock_est = EstadoIntentoRespuesta(
            id=intento_id,
            sprint_id=1,
            tipo="sprint",
            estado="en_curso",
            vidas=4,
            indicadores={"presupuesto": 70, "reputacion": 60, "velocidad": 50, "riesgo_legal": 25},
            respuestas_completadas=3,
            total_tarjetas=10,
            xp_ganada=30,
            monedas_ganadas=15,
            clave_intento="clave_b64",
        )
        with patch.object(JuegoServicio, "obtener_intento", new_callable=AsyncMock) as m_obt:
            m_obt.return_value = mock_est
            resp = client.get(f"/v1/intentos/{intento_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(intento_id)
        assert data["respuestas_completadas"] == 3

    def test_abandonar_intento(self) -> None:
        intento_id = uuid.uuid4()
        mock_ab = AbandonarRespuesta(
            id=intento_id,
            estado="abandonado",
            mensaje="El intento ha sido abandonado.",
        )
        with patch.object(JuegoServicio, "abandonar_intento", new_callable=AsyncMock) as m_ab:
            m_ab.return_value = mock_ab
            resp = client.post(f"/v1/intentos/{intento_id}/abandonar")

        assert resp.status_code == 200
        assert resp.json()["estado"] == "abandonado"


class TestReglasNegocioJuegoServicio:
    def _crear_usuario_test(self, vidas: int = 5, amparo: bool = False) -> Usuario:
        return Usuario(
            id=USUARIO_ID_TEST,
            nombre="Alex Jugador",
            correo="alex@test.com",
            hash_contrasena="hash",
            perfil=PerfilUsuario.desarrollador,
            rol=RolUsuario.jugador,
            estado_cuenta=EstadoCuenta.activo,
            zona_horaria="America/Mexico_City",
            vidas=vidas,
            vidas_base_en=now(),
            monedas=0,
            xp=0,
            nivel=1,
            racha_actual=0,
            racha_maxima=0,
            amparo_activo=amparo,
            preferencias={},
            inventario={"lupa": 0, "abogado": 0, "amparo": 0, "congelar_racha": 0},
            reto_diario={
                "fecha_reto": "2026-11-21",
                "tipo": "aciertos_seguidos",
                "descripcion": "Reto",
                "meta": 3,
                "avance": 0,
                "completado": False,
                "recompensa_monedas": 15,
            },
        )

    def _crear_tarjeta_test(self, tipo: TipoTarjeta = TipoTarjeta.normal) -> Tarjeta:
        return Tarjeta(
            id=uuid.uuid4(),
            version=1,
            sprint_id=1,
            tipo=tipo,
            categoria="datos",
            personaje_nombre="Dev",
            personaje_rol="Frontend",
            iniciales="DEV",
            texto="Caso legal",
            explicacion="Explicacion caso",
            nota_abogado=None,
            array_palabras_trampa=None,
            contenido_interactivo={
                "veredictos": {
                    "legal": {
                        "resultado": "incorrecto",
                        "d_presupuesto": 0,
                        "d_reputacion": -5,
                        "d_velocidad": 10,
                        "d_riesgo": 25,
                    },
                    "ilegal": {
                        "resultado": "correcto",
                        "d_presupuesto": -5,
                        "d_reputacion": 5,
                        "d_velocidad": -10,
                        "d_riesgo": -20,
                    },
                    "condicional": {
                        "resultado": "parcial",
                        "d_presupuesto": 0,
                        "d_reputacion": 0,
                        "d_velocidad": 0,
                        "d_riesgo": 5,
                    },
                    "escalar": {
                        "resultado": "incorrecto",
                        "d_presupuesto": -10,
                        "d_reputacion": 0,
                        "d_velocidad": -5,
                        "d_riesgo": 0,
                    },
                },
                "evidencia": None,
                "micro_pregunta": {
                    "tipo": "por_que",
                    "enunciado": "¿Por qué?",
                    "opciones": [
                        {"id": 1, "texto": "Op 1", "es_correcta": True},
                        {"id": 2, "texto": "Op 2", "es_correcta": False},
                    ],
                },
            },
            activa=True,
            actualizado_en=now(),
        )

    def _crear_intento_test(self, tarjeta_id: uuid.UUID) -> Intento:
        return Intento(
            id=uuid.uuid4(),
            usuario_id=USUARIO_ID_TEST,
            sprint_id=1,
            tipo=TipoIntento.sprint,
            estado=EstadoIntento.en_curso,
            ind_presupuesto=70,
            ind_reputacion=60,
            ind_velocidad=50,
            ind_riesgo=25,
            hp_jefe=None,
            aciertos=0,
            parciales=0,
            errores=0,
            xp_ganada=0,
            monedas_ganadas=0,
            tarjetas_asignadas=[
                {"orden": 1, "tarjeta_id": str(tarjeta_id), "version": 1, "comodines": []}
            ],
            marcado_revision=False,
            pausado_en=None,
            pausa_acumulada_s=0,
        )

    @pytest.mark.asyncio
    async def test_idempotencia_respuesta_devuelve_guardada(self) -> None:
        mock_sesion = AsyncMock()
        servicio = JuegoServicio(mock_sesion)
        usuario = self._crear_usuario_test()
        resp_id = uuid.uuid4()
        intento_id = uuid.uuid4()
        tarjeta_id = uuid.uuid4()

        resp_existente = Respuesta(
            id=resp_id,
            intento_id=intento_id,
            tarjeta_id=tarjeta_id,
            veredicto=None,
            resultado=ResultadoRespuesta.correcto,
            segundos=5.0,
            por_que_ok=True,
            evidencia_ok=False,
            justificacion_ok=False,
            amparo_usado=False,
            d_presupuesto=-5,
            d_reputacion=5,
            d_velocidad=-10,
            d_riesgo=-20,
            xp=15,
            monedas=5,
            vidas_delta=0,
            recibido_en=now(),
        )

        with (
            patch.object(
                servicio._repo, "buscar_usuario_con_lock", new_callable=AsyncMock
            ) as m_usr,
            patch.object(
                servicio._repo, "buscar_respuesta_por_id", new_callable=AsyncMock
            ) as m_resp,
            patch.object(
                servicio._repo, "buscar_intento_por_id", new_callable=AsyncMock
            ) as m_intento,
            patch.object(servicio._repo, "buscar_tarjeta_version", new_callable=AsyncMock) as m_tar,
        ):
            m_usr.return_value = usuario
            m_resp.return_value = resp_existente
            m_intento.return_value = self._crear_intento_test(tarjeta_id)
            m_tar.return_value = self._crear_tarjeta_test()

            from app.esquemas.juego import EnviarRespuestaInput

            datos = EnviarRespuestaInput(
                id=resp_id,
                tarjeta_id=tarjeta_id,
                veredicto="ilegal",
                segundos=5.0,
            )

            res = await servicio.enviar_respuesta(USUARIO_ID_TEST, intento_id, datos)

            assert res.resultado == "correcto"
            assert res.recompensa.xp == 15
            mock_sesion.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_consume_amparo_sin_perder_vida(self) -> None:
        mock_sesion = AsyncMock()
        servicio = JuegoServicio(mock_sesion)
        usuario = self._crear_usuario_test(vidas=5, amparo=True)
        tarjeta = self._crear_tarjeta_test()
        intento = self._crear_intento_test(tarjeta.id)

        with (
            patch.object(
                servicio._repo, "buscar_usuario_con_lock", new_callable=AsyncMock
            ) as m_usr,
            patch.object(
                servicio._repo, "buscar_respuesta_por_id", new_callable=AsyncMock
            ) as m_resp_id,
            patch.object(
                servicio._repo, "buscar_intento_por_id_con_lock", new_callable=AsyncMock
            ) as m_intento,
            patch.object(
                servicio._repo, "buscar_respuesta_por_tarjeta", new_callable=AsyncMock
            ) as m_resp_tar,
            patch.object(servicio._repo, "buscar_tarjeta_version", new_callable=AsyncMock) as m_tar,
            patch.object(servicio._repo, "buscar_sprint", new_callable=AsyncMock) as m_sp,
            patch.object(servicio._repo, "crear_respuesta", new_callable=AsyncMock) as m_crear_r,
            patch.object(
                servicio._repo, "contar_respuestas_intento", new_callable=AsyncMock
            ) as m_contar,
        ):
            m_usr.return_value = usuario
            m_resp_id.return_value = None
            m_intento.return_value = intento
            m_resp_tar.return_value = None
            m_tar.return_value = tarjeta
            m_sp.return_value = Sprint(
                id=1,
                modulo_id=1,
                orden=1,
                es_examen=False,
                titulo="S1",
                objetivo="O1",
                ini_presupuesto=70,
                ini_reputacion=60,
                ini_velocidad=50,
                ini_riesgo=25,
                monedas_max=60,
            )
            m_contar.return_value = 0

            from app.esquemas.juego import EnviarRespuestaInput

            datos = EnviarRespuestaInput(
                id=uuid.uuid4(),
                tarjeta_id=tarjeta.id,
                veredicto="legal",
                segundos=5.0,
            )

            res = await servicio.enviar_respuesta(USUARIO_ID_TEST, intento.id, datos)

            assert res.resultado == "incorrecto"
            assert res.amparo_usado is True
            assert usuario.amparo_activo is False
            assert usuario.vidas == 5

    @pytest.mark.asyncio
    async def test_quiebra_por_riesgo_cierra_intento_sin_monedas(self) -> None:
        mock_sesion = AsyncMock()
        servicio = JuegoServicio(mock_sesion)
        usuario = self._crear_usuario_test(vidas=5)
        tarjeta = self._crear_tarjeta_test()
        intento = self._crear_intento_test(tarjeta.id)
        intento.ind_riesgo = 85

        with (
            patch.object(
                servicio._repo, "buscar_usuario_con_lock", new_callable=AsyncMock
            ) as m_usr,
            patch.object(
                servicio._repo, "buscar_respuesta_por_id", new_callable=AsyncMock
            ) as m_resp_id,
            patch.object(
                servicio._repo, "buscar_intento_por_id_con_lock", new_callable=AsyncMock
            ) as m_intento,
            patch.object(
                servicio._repo, "buscar_respuesta_por_tarjeta", new_callable=AsyncMock
            ) as m_resp_tar,
            patch.object(servicio._repo, "buscar_tarjeta_version", new_callable=AsyncMock) as m_tar,
            patch.object(servicio._repo, "buscar_sprint", new_callable=AsyncMock) as m_sp,
            patch.object(servicio._repo, "crear_respuesta", new_callable=AsyncMock) as m_crear_r,
            patch.object(
                servicio._repo, "contar_respuestas_intento", new_callable=AsyncMock
            ) as m_contar,
            patch.object(
                servicio._repo, "buscar_apelacion_pendiente", new_callable=AsyncMock
            ) as m_apel,
            patch.object(servicio._repo, "crear_apelacion", new_callable=AsyncMock),
            patch.object(servicio._repo, "crear_movimiento_economia", new_callable=AsyncMock),
        ):
            m_usr.return_value = usuario
            m_resp_id.return_value = None
            m_intento.return_value = intento
            m_resp_tar.return_value = None
            m_tar.return_value = tarjeta
            m_sp.return_value = Sprint(
                id=1,
                modulo_id=1,
                orden=1,
                es_examen=False,
                titulo="S1",
                objetivo="O1",
                ini_presupuesto=70,
                ini_reputacion=60,
                ini_velocidad=50,
                ini_riesgo=25,
                monedas_max=60,
            )
            m_contar.return_value = 0
            m_apel.return_value = None

            from app.esquemas.juego import EnviarRespuestaInput

            datos = EnviarRespuestaInput(
                id=uuid.uuid4(),
                tarjeta_id=tarjeta.id,
                veredicto="legal",
                segundos=5.0,
            )

            res = await servicio.enviar_respuesta(USUARIO_ID_TEST, intento.id, datos)

            assert intento.estado == EstadoIntento.quebrado
            assert res.cierre is not None
            assert res.cierre.estado == "quebrado"
            assert res.cierre.estrellas == 0
            assert res.cierre.monedas_acreditadas == 0

    @pytest.mark.asyncio
    async def test_sprint_completado_punta_a_punta_desbloquea_siguiente(self) -> None:
        mock_sesion = AsyncMock()
        servicio = JuegoServicio(mock_sesion)
        usuario = self._crear_usuario_test(vidas=5)
        tarjeta = self._crear_tarjeta_test()
        intento = self._crear_intento_test(tarjeta.id)
        intento.tarjetas_asignadas[0]["orden"] = 10
        intento.aciertos = 9

        sprint_obj = Sprint(
            id=1,
            modulo_id=1,
            orden=1,
            es_examen=False,
            titulo="S1",
            objetivo="O1",
            ini_presupuesto=70,
            ini_reputacion=60,
            ini_velocidad=50,
            ini_riesgo=25,
            monedas_max=60,
        )

        progreso_sprint = ProgresoSprint(
            usuario_id=USUARIO_ID_TEST,
            sprint_id=1,
            estado=EstadoProgreso.disponible,
            estrellas=0,
            mejor_aciertos=0,
            perfecto=False,
        )

        with (
            patch.object(
                servicio._repo, "buscar_usuario_con_lock", new_callable=AsyncMock
            ) as m_usr,
            patch.object(
                servicio._repo, "buscar_respuesta_por_id", new_callable=AsyncMock
            ) as m_resp_id,
            patch.object(
                servicio._repo, "buscar_intento_por_id_con_lock", new_callable=AsyncMock
            ) as m_intento,
            patch.object(
                servicio._repo, "buscar_respuesta_por_tarjeta", new_callable=AsyncMock
            ) as m_resp_tar,
            patch.object(servicio._repo, "buscar_tarjeta_version", new_callable=AsyncMock) as m_tar,
            patch.object(servicio._repo, "buscar_sprint", new_callable=AsyncMock) as m_sp,
            patch.object(servicio._repo, "crear_respuesta", new_callable=AsyncMock),
            patch.object(
                servicio._repo, "contar_respuestas_intento", new_callable=AsyncMock
            ) as m_contar,
            patch.object(servicio._repo, "buscar_progreso", new_callable=AsyncMock) as m_prog,
            patch.object(
                servicio._repo, "desbloquear_siguiente_sprint", new_callable=AsyncMock
            ) as m_desbloquear,
            patch.object(servicio._repo, "otorgar_insignia", new_callable=AsyncMock) as m_insignia,
            patch.object(servicio._repo, "crear_movimiento_economia", new_callable=AsyncMock),
        ):
            m_usr.return_value = usuario
            m_resp_id.return_value = None
            m_intento.return_value = intento
            m_resp_tar.return_value = None
            m_tar.return_value = tarjeta
            m_sp.return_value = sprint_obj
            m_contar.return_value = 9
            m_prog.return_value = progreso_sprint
            m_insignia.return_value = True

            from app.esquemas.juego import EnviarRespuestaInput

            datos = EnviarRespuestaInput(
                id=uuid.uuid4(),
                tarjeta_id=tarjeta.id,
                veredicto="ilegal",
                segundos=4.0,
                por_que_opcion_id=1,
            )

            res = await servicio.enviar_respuesta(USUARIO_ID_TEST, intento.id, datos)

            assert intento.estado == EstadoIntento.completado
            assert res.cierre is not None
            assert res.cierre.estado == "completado"
            assert res.cierre.estrellas == 3
            assert progreso_sprint.estado == EstadoProgreso.completado
            assert progreso_sprint.estrellas == 3
            m_desbloquear.assert_awaited_once_with(USUARIO_ID_TEST, 1, 2)

    @pytest.mark.asyncio
    async def test_enviar_respuesta_evaluacion_incorrecta_y_replay(self) -> None:
        servicio = JuegoServicio(AsyncMock())
        tarjeta = self._crear_tarjeta_test()
        tarjeta_id = tarjeta.id
        intento = self._crear_intento_test(tarjeta_id)
        intento_id = intento.id
        usuario = self._crear_usuario_test(vidas=5)

        with (
            patch.object(
                servicio._repo, "buscar_usuario_con_lock", new_callable=AsyncMock
            ) as m_usr,
            patch.object(
                servicio._repo, "buscar_respuesta_por_id", new_callable=AsyncMock
            ) as m_resp_id,
            patch.object(
                servicio._repo, "buscar_intento_por_id_con_lock", new_callable=AsyncMock
            ) as m_intento,
            patch.object(
                servicio._repo, "buscar_respuesta_por_tarjeta", new_callable=AsyncMock
            ) as m_resp_tar,
            patch.object(servicio._repo, "buscar_tarjeta_version", new_callable=AsyncMock) as m_tar,
            patch.object(servicio._repo, "buscar_sprint", new_callable=AsyncMock) as m_sp,
            patch.object(servicio._repo, "crear_respuesta", new_callable=AsyncMock),
            patch.object(
                servicio._repo, "contar_respuestas_intento", new_callable=AsyncMock
            ) as m_contar,
            patch.object(servicio._repo, "crear_movimiento_economia", new_callable=AsyncMock),
            patch.object(
                servicio._repo, "buscar_apelacion_pendiente", new_callable=AsyncMock
            ) as m_apel,
            patch.object(servicio._repo, "crear_apelacion", new_callable=AsyncMock),
            patch.object(
                servicio._repo, "buscar_intento_por_id", new_callable=AsyncMock
            ) as m_int_id,
        ):
            m_usr.return_value = usuario
            m_resp_id.return_value = None
            m_intento.return_value = intento
            m_resp_tar.return_value = None
            m_tar.return_value = tarjeta
            m_sp.return_value = None
            m_contar.return_value = 0
            m_apel.return_value = None
            m_int_id.return_value = intento

            from app.esquemas.juego import EnviarRespuestaInput

            resp_id = uuid.uuid4()
            datos_incorrectos = EnviarRespuestaInput(
                id=resp_id,
                tarjeta_id=tarjeta_id,
                veredicto="legal",
                segundos=5.0,
            )

            res = await servicio.enviar_respuesta(USUARIO_ID_TEST, intento_id, datos_incorrectos)
            assert res.resultado == "incorrecto"
            assert res.veredicto_correcto == "ilegal"
            assert intento.errores == 1

            saved_resp = Respuesta(
                id=resp_id,
                intento_id=intento_id,
                tarjeta_id=tarjeta_id,
                veredicto=Veredicto.legal,
                resultado=ResultadoRespuesta.incorrecto,
                segundos=5.0,
                por_que_ok=False,
                evidencia_ok=False,
                justificacion_ok=False,
                contraargumento_ok=None,
                amparo_usado=False,
                d_presupuesto=0,
                d_reputacion=-5,
                d_velocidad=10,
                d_riesgo=25,
                xp=0,
                monedas=0,
                vidas_delta=-1,
                respondido_en=now(),
                recibido_en=now(),
            )
            m_resp_id.return_value = saved_resp
            replay = await servicio.enviar_respuesta(USUARIO_ID_TEST, intento_id, datos_incorrectos)
            assert replay.resultado == "incorrecto"
            assert replay.veredicto_correcto == "ilegal"
