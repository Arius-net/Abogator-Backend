# pruebas/integracion/test_auth.py
# Pruebas de integración y seguridad para el dominio de autenticación (06 §1 y §3).

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_config
from app.core.errores import (
    CredencialesInvalidas,
    DemasiasiasPeticiones,
    EmailEnUso,
    NoAutenticado,
    PeticionInvalida,
)
from app.core.reloj import now
from app.core.security import (
    crear_access_token,
    generar_refresh_token,
    hashear_contrasena,
    hashear_token,
)
from app.dominios.auth.servicio import AuthServicio
from app.esquemas.auth import ConsentimientoInput, RegistroInput
from app.main import app
from app.modelos.enums import EstadoCuenta, PerfilUsuario, RolUsuario
from app.modelos.usuarios import RestablecimientoContrasena, SesionRefresh, Usuario

client = TestClient(app)


# ── Fixtures y datos de prueba ────────────────────────────────────────────────


@pytest.fixture
def cfg():
    return get_config()


def _payload_registro(cfg) -> dict:
    return {
        "nombre": "Alex Abogador",
        "correo": "alex@ejemplo.com",
        "contrasena": "Secreto1234!",
        "perfil": "desarrollador",
        "consentimientos": [
            {"documento": "aviso_privacidad", "version": cfg.VERSION_AVISO_PRIVACIDAD},
            {"documento": "terminos", "version": cfg.VERSION_TERMINOS},
        ],
    }


# ── Tests de Endpoints HTTP (/v1/auth) ─────────────────────────────────────────


class TestEndpointsAuth:
    def test_registro_exitoso(self, cfg) -> None:
        payload = _payload_registro(cfg)
        with patch.object(AuthServicio, "registrar", new_callable=AsyncMock) as mock_reg:
            mock_reg.return_value = ("fake_access_token", "fake_refresh_token")
            resp = client.post("/v1/auth/registro", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["access_token"] == "fake_access_token"
        assert data["refresh_token"] == "fake_refresh_token"
        assert data["token_type"] == "bearer"

    def test_registro_correo_duplicado_retorna_409(self, cfg) -> None:
        payload = _payload_registro(cfg)
        with patch.object(AuthServicio, "registrar", new_callable=AsyncMock) as mock_reg:
            mock_reg.side_effect = EmailEnUso()
            resp = client.post("/v1/auth/registro", json=payload)

        assert resp.status_code == 409
        data = resp.json()
        assert data["error"]["codigo"] == "EMAIL_EN_USO"

    def test_registro_consentimiento_faltante_retorna_422_o_400(self, cfg) -> None:
        payload = {
            "nombre": "Alex",
            "correo": "alex@ejemplo.com",
            "contrasena": "Secreto1234!",
            "perfil": "desarrollador",
            "consentimientos": [],  # vacío
        }
        resp = client.post("/v1/auth/registro", json=payload)
        # Validación Pydantic min_length=2 en esquemas/auth.py
        assert resp.status_code == 422

    def test_login_exitoso(self) -> None:
        with (
            patch("app.dominios.auth.router.verificar_rate_login", new_callable=AsyncMock),
            patch.object(AuthServicio, "login", new_callable=AsyncMock) as mock_login,
        ):
            mock_login.return_value = ("access_123", "refresh_123")
            resp = client.post(
                "/v1/auth/login",
                json={"correo": "user@ejemplo.com", "contrasena": "pass123"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "access_123"
        assert data["refresh_token"] == "refresh_123"

    def test_login_credenciales_invalidas_retorna_401(self) -> None:
        with (
            patch("app.dominios.auth.router.verificar_rate_login", new_callable=AsyncMock),
            patch.object(AuthServicio, "login", new_callable=AsyncMock) as mock_login,
        ):
            mock_login.side_effect = CredencialesInvalidas()
            resp = client.post(
                "/v1/auth/login",
                json={"correo": "user@ejemplo.com", "contrasena": "wrong_pass"},
            )

        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["codigo"] == "CREDENCIALES_INVALIDAS"

    def test_login_rate_limit_retorna_429_con_retry_after(self) -> None:
        with patch(
            "app.dominios.auth.router.verificar_rate_login",
            new_callable=AsyncMock,
        ) as mock_rate:
            mock_rate.side_effect = DemasiasiasPeticiones(detalle={"retry_after": 600})
            resp = client.post(
                "/v1/auth/login",
                json={"correo": "user@ejemplo.com", "contrasena": "pass"},
            )

        assert resp.status_code == 429
        assert resp.headers.get("Retry-After") == "600"
        data = resp.json()
        assert data["error"]["codigo"] == "DEMASIADAS_PETICIONES"

    def test_renovar_exitoso(self) -> None:
        with patch.object(AuthServicio, "renovar", new_callable=AsyncMock) as mock_renovar:
            mock_renovar.return_value = ("nuevo_acc", "nuevo_ref")
            resp = client.post(
                "/v1/auth/renovar",
                json={"refresh_token": "token_valido_hex"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "nuevo_acc"
        assert data["refresh_token"] == "nuevo_ref"

    def test_renovar_token_invalido_o_revocado_retorna_401(self) -> None:
        with patch.object(AuthServicio, "renovar", new_callable=AsyncMock) as mock_renovar:
            mock_renovar.side_effect = NoAutenticado()
            resp = client.post(
                "/v1/auth/renovar",
                json={"refresh_token": "token_invalido"},
            )

        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["codigo"] == "NO_AUTENTICADO"

    def test_logout_es_idempotente(self) -> None:
        with patch.object(AuthServicio, "logout", new_callable=AsyncMock) as mock_logout:
            mock_logout.return_value = None
            resp = client.post(
                "/v1/auth/logout",
                json={"refresh_token": "token_a_cerrar"},
            )

        assert resp.status_code == 200
        assert "Sesión cerrada correctamente" in resp.json()["mensaje"]

    def test_recuperar_contrasena_misma_respuesta_exista_o_no(self) -> None:
        """Seguridad OWASP: /recuperar responde siempre exactamente igual."""
        with patch.object(
            AuthServicio, "recuperar_contrasena", new_callable=AsyncMock
        ) as mock_recup:
            mock_recup.return_value = None

            resp1 = client.post("/v1/auth/recuperar", json={"correo": "existe@ejemplo.com"})
            resp2 = client.post("/v1/auth/recuperar", json={"correo": "no_existe@ejemplo.com"})

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json() == resp2.json()
        assert "Si el correo existe, recibirás un enlace" in resp1.json()["mensaje"]

    def test_restablecer_contrasena_exitoso(self) -> None:
        with patch.object(
            AuthServicio, "restablecer_contrasena", new_callable=AsyncMock
        ) as mock_rest:
            mock_rest.return_value = None
            resp = client.post(
                "/v1/auth/restablecer",
                json={"token": "tok_valido", "nueva_contrasena": "NuevaPassword123!"},
            )

        assert resp.status_code == 200
        assert "Contraseña actualizada correctamente" in resp.json()["mensaje"]

    def test_restablecer_contrasena_token_invalido_retorna_400(self) -> None:
        with patch.object(
            AuthServicio, "restablecer_contrasena", new_callable=AsyncMock
        ) as mock_rest:
            mock_rest.side_effect = PeticionInvalida(detalle={"motivo": "Token vencido."})
            resp = client.post(
                "/v1/auth/restablecer",
                json={"token": "tok_invalido", "nueva_contrasena": "NuevaPassword123!"},
            )

        assert resp.status_code == 400
        assert resp.json()["error"]["codigo"] == "PETICION_INVALIDA"


# ── Tests de Seguridad en AuthServicio (Lógica de Negocio) ────────────────────


class TestSeguridadAuthServicio:
    @pytest.mark.asyncio
    async def test_reuso_refresh_token_revoca_toda_la_cadena(self) -> None:
        """
        06 §3 / Requisito Fase 1:
        Si llega un refresh token ya revocado, se detecta reutilización,
        se revoca TODA la cadena para ese usuario y lanza NoAutenticado.
        """
        mock_sesion_db = AsyncMock()
        servicio = AuthServicio(mock_sesion_db)

        # Simulamos que existe una sesión pero YA ESTÁ REVOCADA
        sesion_revocada = SesionRefresh(
            id=uuid.uuid4(),
            usuario_id=uuid.uuid4(),
            token_hash="hash_token_robado",
            revocado_en=now() - timedelta(minutes=5),
            expira_en=now() + timedelta(days=10),
        )

        with (
            patch.object(
                servicio._repo, "buscar_sesion_por_hash", new_callable=AsyncMock
            ) as m_buscar,
            patch.object(
                servicio._repo, "revocar_cadena_de_sesion", new_callable=AsyncMock
            ) as m_revocar_cadena,
        ):
            m_buscar.return_value = sesion_revocada

            with pytest.raises(NoAutenticado):
                await servicio.renovar("token_robado_raw")

            # Verificamos que se revocó toda la cadena
            m_revocar_cadena.assert_awaited_once()
            args = m_revocar_cadena.await_args[0]
            assert args[0] == sesion_revocada.id

    @pytest.mark.asyncio
    async def test_renovacion_valida_rota_token_y_apunta_reemplazado_por(self) -> None:
        """
        Rotación normal: la sesión anterior queda revocada apuntando
        a la nueva_sesion_id con reemplazado_por.
        """
        mock_sesion_db = AsyncMock()
        servicio = AuthServicio(mock_sesion_db)

        usuario_id = uuid.uuid4()
        sesion_activa = SesionRefresh(
            id=uuid.uuid4(),
            usuario_id=usuario_id,
            token_hash="hash_antiguo",
            revocado_en=None,
            expira_en=now() + timedelta(days=10),
        )
        usuario = Usuario(
            id=usuario_id,
            nombre="Jugador",
            correo="jugador@ejemplo.com",
            rol=RolUsuario.jugador,
            perfil=PerfilUsuario.estudiante,
            estado_cuenta=EstadoCuenta.activo,
        )

        with (
            patch.object(
                servicio._repo, "buscar_sesion_por_hash", new_callable=AsyncMock
            ) as m_buscar_sesion,
            patch.object(servicio._repo, "buscar_por_id", new_callable=AsyncMock) as m_buscar_user,
            patch.object(servicio._repo, "revocar_sesion", new_callable=AsyncMock) as m_revocar,
            patch.object(servicio._repo, "crear_sesion", new_callable=AsyncMock) as m_crear_sesion,
        ):
            m_buscar_sesion.return_value = sesion_activa
            m_buscar_user.return_value = usuario

            nuevo_acc, nuevo_ref = await servicio.renovar("token_antiguo_raw")

            assert nuevo_acc is not None
            assert nuevo_ref is not None

            # Debe haber revocado la sesión antigua con reemplazado_por
            m_revocar.assert_awaited_once()
            kwargs = m_revocar.await_args[1]
            assert "reemplazado_por" in kwargs
            assert kwargs["reemplazado_por"] is not None

            # Debe haber creado la nueva sesión
            m_crear_sesion.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_recuperar_contrasena_usuario_inexistente_no_falla_ni_envia(self) -> None:
        """Si el correo no existe, no lanza error ni llama a enviar correo."""
        mock_sesion_db = AsyncMock()
        servicio = AuthServicio(mock_sesion_db)

        with (
            patch.object(servicio._repo, "buscar_por_correo", new_callable=AsyncMock) as m_buscar,
            patch("app.dominios.auth.servicio.get_correo_provider") as m_get_correo,
        ):
            m_buscar.return_value = None
            mock_correo_prov = AsyncMock()
            m_get_correo.return_value = mock_correo_prov

            # No debe lanzar excepción
            await servicio.recuperar_contrasena("fantasma@ejemplo.com")

            mock_correo_prov.enviar_recuperacion.assert_not_called()

    @pytest.mark.asyncio
    async def test_restablecer_contrasena_revoca_todas_las_sesiones(self) -> None:
        """Al restablecer contraseña con éxito, todas las sesiones activas se revocan."""
        mock_sesion_db = AsyncMock()
        servicio = AuthServicio(mock_sesion_db)

        usuario_id = uuid.uuid4()
        usuario = Usuario(
            id=usuario_id,
            nombre="Jugador",
            correo="jugador@ejemplo.com",
            hash_contrasena=hashear_contrasena("ViejaPass123!"),
            rol=RolUsuario.jugador,
            perfil=PerfilUsuario.estudiante,
            estado_cuenta=EstadoCuenta.activo,
        )
        reset = RestablecimientoContrasena(
            id=uuid.uuid4(),
            usuario_id=usuario_id,
            token_hash="hash_reset",
            expira_en=now() + timedelta(minutes=15),
            usado_en=None,
        )

        with (
            patch.object(
                servicio._repo, "buscar_restablecimiento_por_hash", new_callable=AsyncMock
            ) as m_buscar_reset,
            patch.object(servicio._repo, "buscar_por_id", new_callable=AsyncMock) as m_buscar_user,
            patch.object(
                servicio._repo, "revocar_todas_sesiones_usuario", new_callable=AsyncMock
            ) as m_revocar_todas,
        ):
            m_buscar_reset.return_value = reset
            m_buscar_user.return_value = usuario

            await servicio.restablecer_contrasena("token_raw", "NuevaPassword999!")

            assert reset.usado_en is not None
            m_revocar_todas.assert_awaited_once_with(usuario_id, reset.usado_en)
