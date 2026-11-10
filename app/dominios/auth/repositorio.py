from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos.usuarios import (
    Consentimiento,
    DispositivoPush,
    RestablecimientoContrasena,
    SesionRefresh,
    Usuario,
)


class AuthRepositorio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion


    async def buscar_por_correo(self, correo: str) -> Usuario | None:
        resultado = await self._s.execute(
            select(Usuario).where(Usuario.correo == correo)
        )
        return resultado.scalar_one_or_none()

    async def buscar_por_id(self, usuario_id: uuid.UUID) -> Usuario | None:
        return await self._s.get(Usuario, usuario_id)

    async def crear_usuario(self, usuario: Usuario) -> None:
        self._s.add(usuario)


    async def crear_consentimiento(self, consentimiento: Consentimiento) -> None:
        self._s.add(consentimiento)


    async def buscar_sesion_por_hash(self, token_hash: str) -> SesionRefresh | None:
        resultado = await self._s.execute(
            select(SesionRefresh).where(SesionRefresh.token_hash == token_hash)
        )
        return resultado.scalar_one_or_none()

    async def crear_sesion(self, sesion: SesionRefresh) -> None:
        self._s.add(sesion)

    async def revocar_sesion(
        self,
        sesion_id: uuid.UUID,
        ahora: datetime,
        reemplazado_por: uuid.UUID | None = None,
    ) -> None:
        await self._s.execute(
            update(SesionRefresh)
            .where(SesionRefresh.id == sesion_id)
            .values(revocado_en=ahora, reemplazado_por=reemplazado_por)
        )

    async def revocar_todas_sesiones_usuario(
        self, usuario_id: uuid.UUID, ahora: datetime
    ) -> None:
        """Revoca toda la cadena de sesiones del usuario (reutilización de token / restablecer)."""
        await self._s.execute(
            update(SesionRefresh)
            .where(
                SesionRefresh.usuario_id == usuario_id,
                SesionRefresh.revocado_en.is_(None),
            )
            .values(revocado_en=ahora)
        )

    async def revocar_cadena_de_sesion(
        self, sesion_id: uuid.UUID, ahora: datetime
    ) -> None:
        """
        Cuando se detecta reutilización de un refresh token ya revocado,
        se revoca toda la cadena de sesiones de ese usuario (06 §3).
        """
        sesion = await self._s.get(SesionRefresh, sesion_id)
        if sesion is None:
            return
        await self.revocar_todas_sesiones_usuario(sesion.usuario_id, ahora)


    async def buscar_restablecimiento_por_hash(
        self, token_hash: str
    ) -> RestablecimientoContrasena | None:
        resultado = await self._s.execute(
            select(RestablecimientoContrasena).where(
                RestablecimientoContrasena.token_hash == token_hash,
            )
        )
        return resultado.scalar_one_or_none()

    async def crear_restablecimiento(self, r: RestablecimientoContrasena) -> None:
        self._s.add(r)

    async def invalidar_restablecimientos_previos(
        self, usuario_id: uuid.UUID, ahora: datetime
    ) -> None:
        """Marca como usados todos los tokens de recuperación vigentes del usuario."""
        await self._s.execute(
            update(RestablecimientoContrasena)
            .where(
                RestablecimientoContrasena.usuario_id == usuario_id,
                RestablecimientoContrasena.usado_en.is_(None),
            )
            .values(usado_en=ahora)
        )
