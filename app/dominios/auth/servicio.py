from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_config
from app.core.correo import get_correo_provider
from app.core.errores import (
    CredencialesInvalidas,
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
    verificar_contrasena,
)
from app.dominios.auth.repositorio import AuthRepositorio
from app.dominios.usuarios.repositorio import UsuariosRepositorio
from app.esquemas.auth import ConsentimientoInput, RegistroInput
from app.esquemas.jsonb import Inventario, Preferencias, RetoDiario
from app.modelos.enums import EstadoCuenta, PerfilUsuario, RolUsuario
from app.modelos.usuarios import (
    Consentimiento,
    RestablecimientoContrasena,
    SesionRefresh,
    Usuario,
)


class AuthServicio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion
        self._repo = AuthRepositorio(sesion)
        self._repo_usr = UsuariosRepositorio(sesion)

    async def registrar(
        self,
        datos: RegistroInput,
        ip: str | None,
        version_aviso: str,
        version_terminos: str,
    ) -> tuple[str, str]:
        """
        Crea la cuenta, guarda los 2 consentimientos, inicializa el estado del
        jugador (vidas=5, sprint 1 módulo 1 disponible) y devuelve (access, refresh).
        """
        cfg = get_config()

        consentimientos_input = {c.documento: c for c in datos.consentimientos}
        for doc, version_esperada in [
            ("aviso_privacidad", version_aviso),
            ("terminos", version_terminos),
        ]:
            if doc not in consentimientos_input:
                from app.core.errores import PeticionInvalida

                raise PeticionInvalida(
                    detalle={"campo": "consentimientos", "motivo": f"Falta el documento '{doc}'"}
                )
            if consentimientos_input[doc].version != version_esperada:
                from app.core.errores import PeticionInvalida

                raise PeticionInvalida(
                    detalle={
                        "campo": "consentimientos",
                        "motivo": f"Versión inválida para '{doc}'. Esperada: {version_esperada}",
                    }
                )

        existente = await self._repo.buscar_por_correo(str(datos.correo))
        if existente is not None:
            raise EmailEnUso()

        ahora = now()
        fecha_hoy = ahora.date()

        preferencias = Preferencias.por_defecto()
        inventario = Inventario.vacio()
        reto_hoy = RetoDiario.de_hoy(fecha_hoy)

        usuario = Usuario(
            id=uuid.uuid4(),
            nombre=datos.nombre,
            correo=str(datos.correo),
            hash_contrasena=hashear_contrasena(datos.contrasena),
            perfil=PerfilUsuario(datos.perfil),
            rol=RolUsuario.jugador,
            estado_cuenta=EstadoCuenta.activo,
            zona_horaria="America/Mexico_City",
            vidas=cfg.VIDAS_MAX,
            vidas_base_en=ahora,
            monedas=0,
            xp=0,
            nivel=1,
            racha_actual=0,
            racha_maxima=0,
            amparo_activo=False,
            preferencias=preferencias.model_dump(),
            inventario=inventario.model_dump(),
            reto_diario=reto_hoy.model_dump(mode="json"),
        )
        await self._repo.crear_usuario(usuario)
        await self._s.flush()

        for doc, con_input in consentimientos_input.items():
            await self._repo.crear_consentimiento(
                Consentimiento(
                    usuario_id=usuario.id,
                    documento=doc,
                    version=con_input.version,
                    aceptado_en=ahora,
                    ip=ip,
                )
            )

        await self._repo_usr.desbloquear_sprint_inicial(usuario.id)
        await self._s.flush()

        access, refresh, _ = await self._crear_sesion(
            usuario=usuario,
            dispositivo=None,
            ahora=ahora,
        )

        await self._s.commit()
        return access, refresh

    async def login(
        self,
        correo: str,
        contrasena: str,
        dispositivo: str | None,
    ) -> tuple[str, str]:
        usuario = await self._repo.buscar_por_correo(correo)
        if usuario is None or not verificar_contrasena(contrasena, usuario.hash_contrasena):
            raise CredencialesInvalidas()
        if usuario.estado_cuenta != EstadoCuenta.activo:
            raise CredencialesInvalidas()

        ahora = now()
        usuario.ultimo_acceso = ahora

        access, refresh, _ = await self._crear_sesion(
            usuario=usuario,
            dispositivo=dispositivo,
            ahora=ahora,
        )
        await self._s.commit()
        return access, refresh

    async def renovar(self, refresh_token_raw: str) -> tuple[str, str]:
        cfg = get_config()
        token_hash = hashear_token(refresh_token_raw)
        sesion = await self._repo.buscar_sesion_por_hash(token_hash)

        if sesion is None:
            raise NoAutenticado()

        ahora = now()

        if sesion.revocado_en is not None:
            await self._repo.revocar_cadena_de_sesion(sesion.id, ahora)
            await self._s.commit()
            raise NoAutenticado()

        if sesion.expira_en < ahora:
            await self._repo.revocar_sesion(sesion.id, ahora)
            await self._s.commit()
            raise NoAutenticado()

        usuario = await self._repo.buscar_por_id(sesion.usuario_id)
        if usuario is None or usuario.estado_cuenta != EstadoCuenta.activo:
            raise NoAutenticado()

        nueva_sesion_id = uuid.uuid4()
        await self._repo.revocar_sesion(sesion.id, ahora, reemplazado_por=nueva_sesion_id)

        nuevo_refresh_raw = generar_refresh_token()
        nuevo_hash = hashear_token(nuevo_refresh_raw)
        nueva_sesion = SesionRefresh(
            id=nueva_sesion_id,
            usuario_id=usuario.id,
            token_hash=nuevo_hash,
            dispositivo=sesion.dispositivo,
            expira_en=ahora + timedelta(days=cfg.REFRESH_TOKEN_DIAS),
        )
        await self._repo.crear_sesion(nueva_sesion)

        nuevo_access = crear_access_token(
            sub=str(usuario.id),
            rol=usuario.rol.value,
            perfil=usuario.perfil.value,
        )

        await self._s.commit()
        return nuevo_access, nuevo_refresh_raw

    async def logout(self, refresh_token_raw: str) -> None:
        token_hash = hashear_token(refresh_token_raw)
        sesion = await self._repo.buscar_sesion_por_hash(token_hash)
        if sesion is None or sesion.revocado_en is not None:
            return  # idempotente

        await self._repo.revocar_sesion(sesion.id, now())
        await self._s.commit()

    async def recuperar_contrasena(self, correo: str) -> None:
        """
        Genera un token de un solo uso y envía el correo.
        Siempre responde igual exista o no el correo (06 §3).
        """
        cfg = get_config()
        usuario = await self._repo.buscar_por_correo(correo)
        if usuario is None:
            return

        ahora = now()
        await self._repo.invalidar_restablecimientos_previos(usuario.id, ahora)

        token_raw = secrets.token_urlsafe(32)
        token_hash = hashear_token(token_raw)
        expira = ahora + timedelta(minutes=30)

        await self._repo.crear_restablecimiento(
            RestablecimientoContrasena(
                id=uuid.uuid4(),
                usuario_id=usuario.id,
                token_hash=token_hash,
                expira_en=expira,
            )
        )
        await self._s.commit()

        enlace = f"{cfg.API_BASE_URL}/v1/auth/restablecer?token={token_raw}"
        proveedor = get_correo_provider()
        await proveedor.enviar_recuperacion(
            destinatario=correo,
            nombre=usuario.nombre,
            enlace=enlace,
        )

    async def restablecer_contrasena(self, token_raw: str, nueva_contrasena: str) -> None:
        token_hash = hashear_token(token_raw)
        reset = await self._repo.buscar_restablecimiento_por_hash(token_hash)

        ahora = now()

        if reset is None:
            raise PeticionInvalida(detalle={"motivo": "Token inválido o ya utilizado."})
        if reset.usado_en is not None:
            raise PeticionInvalida(detalle={"motivo": "Token inválido o ya utilizado."})
        if reset.expira_en < ahora:
            raise PeticionInvalida(detalle={"motivo": "Token vencido."})

        usuario = await self._repo.buscar_por_id(reset.usuario_id)
        if usuario is None:
            raise PeticionInvalida(detalle={"motivo": "Token inválido."})

        usuario.hash_contrasena = hashear_contrasena(nueva_contrasena)
        reset.usado_en = ahora

        await self._repo.revocar_todas_sesiones_usuario(usuario.id, ahora)
        await self._s.commit()

    async def _crear_sesion(
        self,
        usuario: Usuario,
        dispositivo: str | None,
        ahora: datetime,
    ) -> tuple[str, str, SesionRefresh]:
        cfg = get_config()
        refresh_raw = generar_refresh_token()
        refresh_hash = hashear_token(refresh_raw)
        sesion_id = uuid.uuid4()

        sesion = SesionRefresh(
            id=sesion_id,
            usuario_id=usuario.id,
            token_hash=refresh_hash,
            dispositivo=dispositivo,
            expira_en=ahora + timedelta(days=cfg.REFRESH_TOKEN_DIAS),
        )
        await self._repo.crear_sesion(sesion)

        access = crear_access_token(
            sub=str(usuario.id),
            rol=usuario.rol.value,
            perfil=usuario.perfil.value,
        )
        return access, refresh_raw, sesion
