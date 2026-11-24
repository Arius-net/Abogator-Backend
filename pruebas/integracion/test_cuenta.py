# pruebas/integracion/test_cuenta.py
# Pruebas de integración y seguridad para los endpoints de cuenta (06 §1 — Cuenta).
# Incluye prueba de soft-delete (Regla de Oro 6) y exportación ARCO.

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.deps import usuario_actual
from app.core.errores import NoEncontrado
from app.core.reloj import now
from app.dominios.usuarios.servicio import UsuariosServicio
from app.esquemas.jsonb import Inventario, Preferencias, RetoDiario
from app.esquemas.usuario import (
    ActualizarCuentaInput,
    DatosPersonalesRespuesta,
    DispositivoRespuesta,
    EstadoRespuesta,
    InventarioRespuesta,
    MovimientosPaginados,
    PerfilRespuesta,
    RetoRespuesta,
    UsuarioRespuesta,
)
from app.main import app
from app.modelos.enums import EstadoCuenta, PerfilUsuario, RolUsuario
from app.modelos.usuarios import Usuario

client = TestClient(app)

USUARIO_ID_TEST = uuid.uuid4()


@pytest.fixture(autouse=True)
def override_usuario_autenticado():
    """Autentica por defecto al usuario de prueba en todos los endpoints /me."""
    app.dependency_overrides[usuario_actual] = lambda: {
        "sub": str(USUARIO_ID_TEST),
        "rol": "jugador",
        "perfil": "desarrollador",
    }
    yield
    app.dependency_overrides.pop(usuario_actual, None)


# ── Tests de Endpoints HTTP (/v1/me) ──────────────────────────────────────────


class TestEndpointsCuenta:
    def test_obtener_me_exitoso(self) -> None:
        usr_mock = UsuarioRespuesta(
            id=USUARIO_ID_TEST,
            nombre="Alex Abogado",
            correo="alex@ejemplo.com",
            perfil="desarrollador",
            rol="jugador",
            estado_cuenta="activo",
            zona_horaria="America/Mexico_City",
            nivel=1,
            xp=0,
            monedas=100,
            racha_actual=2,
            racha_maxima=5,
            creado_en=now(),
            ultimo_acceso=now(),
        )
        with patch.object(UsuariosServicio, "obtener_usuario", new_callable=AsyncMock) as m_get:
            m_get.return_value = usr_mock
            resp = client.get("/v1/me")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(USUARIO_ID_TEST)
        assert data["nombre"] == "Alex Abogado"
        assert data["correo"] == "alex@ejemplo.com"

    def test_actualizar_me_nombre_y_perfil(self) -> None:
        usr_mock = UsuarioRespuesta(
            id=USUARIO_ID_TEST,
            nombre="Alex Actualizado",
            correo="alex@ejemplo.com",
            perfil="legal",
            rol="jugador",
            estado_cuenta="activo",
            zona_horaria="America/Mexico_City",
            nivel=1,
            xp=0,
            monedas=100,
            racha_actual=2,
            racha_maxima=5,
            creado_en=now(),
            ultimo_acceso=now(),
        )
        with patch.object(UsuariosServicio, "actualizar_cuenta", new_callable=AsyncMock) as m_upd:
            m_upd.return_value = usr_mock
            resp = client.patch(
                "/v1/me",
                json={"nombre": "Alex Actualizado", "perfil": "legal"},
            )

        assert resp.status_code == 200
        assert resp.json()["nombre"] == "Alex Actualizado"
        assert resp.json()["perfil"] == "legal"

    def test_actualizar_me_perfil_invalido_retorna_422(self) -> None:
        resp = client.patch("/v1/me", json={"perfil": "hacker_invalido"})
        assert resp.status_code == 422

    def test_estado_me_calcula_vidas_efectivas(self) -> None:
        estado_mock = EstadoRespuesta(
            vidas=4,
            vidas_max=5,
            proxima_vida_en=now() + timedelta(minutes=45),
            monedas=250,
            xp=150,
            nivel=2,
            racha_actual=3,
            amparo_activo=False,
        )
        with patch.object(UsuariosServicio, "estado_usuario", new_callable=AsyncMock) as m_est:
            m_est.return_value = estado_mock
            resp = client.get("/v1/me/estado")

        assert resp.status_code == 200
        data = resp.json()
        assert data["vidas"] == 4
        assert data["vidas_max"] == 5
        assert data["proxima_vida_en"] is not None
        assert data["monedas"] == 250

    def test_guardar_preferencias(self) -> None:
        nuevas_prefs = Preferencias(
            modo_oscuro=True,
            escala_texto=1.5,
            haptica=False,
        )
        with patch.object(
            UsuariosServicio, "guardar_preferencias", new_callable=AsyncMock
        ) as m_pref:
            m_pref.return_value = nuevas_prefs
            resp = client.put(
                "/v1/me/preferencias",
                json=nuevas_prefs.model_dump(),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["modo_oscuro"] is True
        assert data["escala_texto"] == 1.5
        assert data["haptica"] is False

    def test_guardar_preferencias_clave_desconocida_rechazada(self) -> None:
        """Regla de Oro 5: extra='forbid' rechaza claves desconocidas."""
        payload = Preferencias.por_defecto().model_dump()
        payload["clave_invalida_que_no_existe"] = "inyeccion"
        resp = client.put("/v1/me/preferencias", json=payload)
        assert resp.status_code == 422

    def test_registrar_dispositivo(self) -> None:
        disp_id = uuid.uuid4()
        with patch.object(
            UsuariosServicio, "registrar_dispositivo", new_callable=AsyncMock
        ) as m_disp:
            m_disp.return_value = DispositivoRespuesta(
                id=disp_id, plataforma="android", activo=True
            )
            resp = client.post(
                "/v1/me/dispositivos",
                json={"plataforma": "android", "token": "fcm_token_123"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == str(disp_id)
        assert data["plataforma"] == "android"
        assert data["activo"] is True

    def test_exportar_datos_personales_arco(self) -> None:
        datos_mock = DatosPersonalesRespuesta(
            id=USUARIO_ID_TEST,
            nombre="Alex Abogado",
            correo="alex@ejemplo.com",
            perfil="desarrollador",
            zona_horaria="America/Mexico_City",
            creado_en=now(),
            consentimientos=[
                {
                    "documento": "aviso_privacidad",
                    "version": "v1.0",
                    "aceptado_en": now().isoformat(),
                    "ip": "127.0.0.1",
                }
            ],
            dispositivos_push=[],
        )
        with patch.object(UsuariosServicio, "exportar_datos", new_callable=AsyncMock) as m_arco:
            m_arco.return_value = datos_mock
            resp = client.get("/v1/me/datos")

        assert resp.status_code == 200
        data = resp.json()
        assert data["correo"] == "alex@ejemplo.com"
        assert len(data["consentimientos"]) == 1

    def test_borrar_cuenta_soft_delete_endpoint(self) -> None:
        """Endpoint DELETE /me retorna 204 No Content."""
        with patch.object(UsuariosServicio, "solicitar_borrado", new_callable=AsyncMock) as m_del:
            m_del.return_value = None
            resp = client.delete("/v1/me")

        assert resp.status_code == 204
        m_del.assert_awaited_once_with(USUARIO_ID_TEST)

    def test_inventario_usuario(self) -> None:
        inv_mock = InventarioRespuesta(inventario=Inventario(lupa=2, abogado=1))
        with patch.object(UsuariosServicio, "inventario_usuario", new_callable=AsyncMock) as m_inv:
            m_inv.return_value = inv_mock
            resp = client.get("/v1/me/inventario")

        assert resp.status_code == 200
        data = resp.json()
        assert data["inventario"]["lupa"] == 2
        assert data["inventario"]["abogado"] == 1
        assert data["inventario"]["amparo"] == 0

    def test_reto_diario_hoy(self) -> None:
        reto_mock = RetoRespuesta(
            fecha_reto=now().date(),
            tipo="sprints_completados",
            descripcion="Completa 1 sprint",
            meta=1,
            avance=0,
            completado=False,
            recompensa_monedas=15,
        )
        with patch.object(UsuariosServicio, "reto_hoy", new_callable=AsyncMock) as m_reto:
            m_reto.return_value = reto_mock
            resp = client.get("/v1/retos/hoy")

        assert resp.status_code == 200
        assert resp.json()["tipo"] == "sprints_completados"
        assert resp.json()["meta"] == 1


# ── Tests de Lógica de Negocio y Seguridad (Soft-Delete RG6) ──────────────────


class TestSeguridadSoftDelete:
    @pytest.mark.asyncio
    async def test_solicitar_borrado_aplica_soft_delete_y_revoca_sesiones(self) -> None:
        """
        Regla de Oro 6 / Criterio de término Fase 1:
        NUNCA un DELETE FROM usuarios.
        El usuario pasa a estado_cuenta = 'pendiente_borrado',
        se llena eliminado_en = now(), y se revocan TODAS las sesiones activas.
        """
        mock_sesion_db = AsyncMock()
        servicio = UsuariosServicio(mock_sesion_db)

        usuario = Usuario(
            id=USUARIO_ID_TEST,
            nombre="Jugador Por Borrar",
            correo="borrar@ejemplo.com",
            estado_cuenta=EstadoCuenta.activo,
            eliminado_en=None,
        )

        with (
            patch.object(
                servicio._repo, "buscar_con_lock", new_callable=AsyncMock
            ) as m_buscar_lock,
            patch(
                "app.dominios.auth.repositorio.AuthRepositorio.revocar_todas_sesiones_usuario",
                new_callable=AsyncMock,
            ) as m_revocar_sesiones,
        ):
            m_buscar_lock.return_value = usuario

            await servicio.solicitar_borrado(USUARIO_ID_TEST)

            # 1. Soft-delete verificado: no se elimina el registro, cambia su estado
            assert usuario.estado_cuenta == EstadoCuenta.pendiente_borrado
            assert usuario.eliminado_en is not None

            # 2. Todas las sesiones de refresh quedan revocadas
            m_revocar_sesiones.assert_awaited_once()
            args = m_revocar_sesiones.await_args[0]
            assert args[0] == USUARIO_ID_TEST

            # 3. Transacción confirmada
            mock_sesion_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_usuario_pendiente_borrado_no_puede_loguearse(self) -> None:
        """Una cuenta en estado pendiente_borrado es rechazada en login."""
        from app.dominios.auth.servicio import AuthServicio
        from app.core.errores import CredencialesInvalidas
        from app.core.security import hashear_contrasena

        mock_sesion_db = AsyncMock()
        auth_servicio = AuthServicio(mock_sesion_db)

        usuario = Usuario(
            id=USUARIO_ID_TEST,
            nombre="Borrado",
            correo="borrado@ejemplo.com",
            hash_contrasena=hashear_contrasena("Pass123!"),
            estado_cuenta=EstadoCuenta.pendiente_borrado,
        )

        with patch.object(
            auth_servicio._repo, "buscar_por_correo", new_callable=AsyncMock
        ) as m_buscar:
            m_buscar.return_value = usuario

            with pytest.raises(CredencialesInvalidas):
                await auth_servicio.login("borrado@ejemplo.com", "Pass123!", None)
