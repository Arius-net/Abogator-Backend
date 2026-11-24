from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.deps import usuario_actual
from app.core.errores import PeticionInvalida
from app.core.reloj import now
from app.dominios.admin.servicio import AdminServicio
from app.esquemas.admin import (
    ComodinAdminRespuesta,
    MetricasAdminRespuesta,
    TarjetaAdminRespuesta,
)
from app.esquemas.contenido import ContenidoInteractivo
from app.main import app
from app.modelos.contenido import Sprint, Tarjeta
from app.modelos.enums import TipoTarjeta

client = TestClient(app)
ADMIN_ID_TEST = uuid.uuid4()


@pytest.fixture(autouse=True)
def override_admin_auth():
    app.dependency_overrides[usuario_actual] = lambda: {
        "sub": str(ADMIN_ID_TEST),
        "rol": "admin",
        "perfil": "desarrollador",
    }
    yield
    app.dependency_overrides.pop(usuario_actual, None)


def _crear_contenido_interactivo_dict() -> dict:
    return {
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
    }


class TestAdminEndpoints:
    def test_acceso_denegado_para_rol_jugador(self) -> None:
        app.dependency_overrides[usuario_actual] = lambda: {
            "sub": str(uuid.uuid4()),
            "rol": "jugador",
            "perfil": "desarrollador",
        }
        resp = client.get("/v1/admin/tarjetas")
        assert resp.status_code == 403
        assert resp.json()["error"]["codigo"] == "SIN_PERMISO"

    def test_listar_tarjetas(self) -> None:
        tarjeta_mock = TarjetaAdminRespuesta(
            id=uuid.uuid4(),
            version=1,
            sprint_id=1,
            tipo="normal",
            categoria="datos",
            personaje_nombre="Dev",
            personaje_rol="Frontend",
            iniciales="DEV",
            texto="Texto caso",
            explicacion="Expl",
            nota_abogado=None,
            array_palabras_trampa=None,
            contenido_interactivo=_crear_contenido_interactivo_dict(),
            activa=True,
            actualizado_en=now(),
        )
        with patch.object(AdminServicio, "listar_tarjetas", new_callable=AsyncMock) as m_list:
            m_list.return_value = [tarjeta_mock]
            resp = client.get("/v1/admin/tarjetas")

        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_crear_tarjeta_inicia_inactiva_version_uno(self) -> None:
        tarjeta_id = uuid.uuid4()
        tarjeta_mock = TarjetaAdminRespuesta(
            id=tarjeta_id,
            version=1,
            sprint_id=1,
            tipo="normal",
            categoria="datos",
            personaje_nombre="Dev",
            personaje_rol="Frontend",
            iniciales="DEV",
            texto="Texto caso",
            explicacion="Expl",
            nota_abogado=None,
            array_palabras_trampa=None,
            contenido_interactivo=_crear_contenido_interactivo_dict(),
            activa=False,
            actualizado_en=now(),
        )
        with patch.object(AdminServicio, "crear_tarjeta", new_callable=AsyncMock) as m_crear:
            m_crear.return_value = tarjeta_mock
            payload = {
                "sprint_id": 1,
                "tipo": "normal",
                "categoria": "datos",
                "personaje_nombre": "Dev",
                "personaje_rol": "Frontend",
                "iniciales": "DEV",
                "texto": "Texto caso",
                "explicacion": "Expl",
                "contenido_interactivo": _crear_contenido_interactivo_dict(),
            }
            resp = client.post("/v1/admin/tarjetas", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["version"] == 1
        assert data["activa"] is False

    def test_cambiar_estado_tarjeta(self) -> None:
        tarjeta_id = uuid.uuid4()
        tarjeta_mock = TarjetaAdminRespuesta(
            id=tarjeta_id,
            version=1,
            sprint_id=1,
            tipo="normal",
            categoria="datos",
            personaje_nombre="Dev",
            personaje_rol="Frontend",
            iniciales="DEV",
            texto="Texto caso",
            explicacion="Expl",
            nota_abogado=None,
            array_palabras_trampa=None,
            contenido_interactivo=_crear_contenido_interactivo_dict(),
            activa=True,
            actualizado_en=now(),
        )
        with patch.object(AdminServicio, "cambiar_estado_tarjeta", new_callable=AsyncMock) as m_est:
            m_est.return_value = tarjeta_mock
            resp = client.patch(
                f"/v1/admin/tarjetas/{tarjeta_id}/estado",
                json={"activa": True},
            )

        assert resp.status_code == 200
        assert resp.json()["activa"] is True

    def test_actualizar_comodin(self) -> None:
        com_mock = ComodinAdminRespuesta(
            clave="lupa",
            nombre="Lupa",
            descripcion="Desc",
            precio=75,
            permitido_en_examen=False,
            activo=True,
        )
        with patch.object(AdminServicio, "actualizar_comodin", new_callable=AsyncMock) as m_com:
            m_com.return_value = com_mock
            resp = client.put(
                "/v1/admin/comodines/lupa",
                json={"precio": 75},
            )

        assert resp.status_code == 200
        assert resp.json()["precio"] == 75

    def test_metricas_admin(self) -> None:
        met_mock = MetricasAdminRespuesta(
            tasa_acierto_tarjetas=[
                {"tarjeta_id": str(uuid.uuid4()), "total": 10, "tasa_acierto": 80.0}
            ],
            quiebras_por_sprint=[{"sprint_id": 1, "quiebras": 2}],
            retencion_apelaciones={"tasa_retencion": 0.0, "total_apelaciones": 0},
        )
        with patch.object(AdminServicio, "metricas", new_callable=AsyncMock) as m_met:
            m_met.return_value = met_mock
            resp = client.get("/v1/admin/metricas")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasa_acierto_tarjetas"]) == 1


class TestInmutabilidadTarjetaReglaDos:
    @pytest.mark.asyncio
    async def test_editar_tarjeta_clona_version_nueva_y_desactiva_vieja(self) -> None:
        mock_sesion_db = AsyncMock()
        servicio = AdminServicio(mock_sesion_db)

        id_vieja = uuid.uuid4()
        tarjeta_vieja = Tarjeta(
            id=id_vieja,
            version=1,
            sprint_id=1,
            tipo=TipoTarjeta.normal,
            categoria="datos",
            personaje_nombre="Dev",
            personaje_rol="Frontend",
            iniciales="DEV",
            texto="Texto v1",
            explicacion="Expl v1",
            nota_abogado=None,
            array_palabras_trampa=None,
            contenido_interactivo=_crear_contenido_interactivo_dict(),
            activa=True,
            actualizado_en=now(),
        )

        with (
            patch.object(
                servicio._repo, "buscar_tarjeta_por_id", new_callable=AsyncMock
            ) as m_buscar,
            patch.object(servicio._repo, "crear_tarjeta", new_callable=AsyncMock) as m_crear,
            patch.object(servicio._repo, "registrar_auditoria", new_callable=AsyncMock) as m_audit,
        ):
            m_buscar.return_value = tarjeta_vieja

            from app.esquemas.admin import EditarTarjetaInput

            datos = EditarTarjetaInput(texto="Texto v2 editado")

            res = await servicio.editar_tarjeta(ADMIN_ID_TEST, id_vieja, datos)

            assert tarjeta_vieja.activa is False

            m_crear.assert_awaited_once()
            tarjeta_nueva: Tarjeta = m_crear.await_args[0][0]

            assert tarjeta_nueva.id != id_vieja
            assert tarjeta_nueva.version == 2
            assert tarjeta_nueva.activa is True
            assert tarjeta_nueva.texto == "Texto v2 editado"
            assert tarjeta_nueva.explicacion == "Expl v1"

            m_audit.assert_awaited_once()
            audit_kwargs = m_audit.await_args[1]
            assert audit_kwargs["accion"] == "editar"
            assert audit_kwargs["entidad"] == "tarjeta"
            assert audit_kwargs["entidad_id"] == str(tarjeta_nueva.id)

    @pytest.mark.asyncio
    async def test_editar_tarjeta_inactiva_falla(self) -> None:
        mock_sesion_db = AsyncMock()
        servicio = AdminServicio(mock_sesion_db)

        id_vieja = uuid.uuid4()
        tarjeta_inactiva = Tarjeta(
            id=id_vieja,
            version=1,
            sprint_id=1,
            tipo=TipoTarjeta.normal,
            categoria="datos",
            personaje_nombre="Dev",
            personaje_rol="Frontend",
            iniciales="DEV",
            texto="Texto v1",
            explicacion="Expl v1",
            contenido_interactivo=_crear_contenido_interactivo_dict(),
            activa=False,
            actualizado_en=now(),
        )

        with patch.object(
            servicio._repo, "buscar_tarjeta_por_id", new_callable=AsyncMock
        ) as m_buscar:
            m_buscar.return_value = tarjeta_inactiva

            from app.esquemas.admin import EditarTarjetaInput

            datos = EditarTarjetaInput(texto="Texto v2")

            with pytest.raises(PeticionInvalida):
                await servicio.editar_tarjeta(ADMIN_ID_TEST, id_vieja, datos)
