from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modelos.economia import MovimientoEconomia
from app.modelos.juego import ProgresoSprint
from app.modelos.logros import Certificado, Insignia, UsuarioInsignia
from app.modelos.usuarios import Consentimiento, DispositivoPush, Usuario


class UsuariosRepositorio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def buscar_por_id(self, usuario_id: uuid.UUID) -> Usuario | None:
        return await self._s.get(Usuario, usuario_id)

    async def buscar_con_lock(self, usuario_id: uuid.UUID) -> Usuario | None:
        """SELECT … FOR UPDATE: usar cuando se toca economía (Regla de Oro 3)."""
        resultado = await self._s.execute(
            select(Usuario).where(Usuario.id == usuario_id).with_for_update()
        )
        return resultado.scalar_one_or_none()

    async def desbloquear_sprint_inicial(self, usuario_id: uuid.UUID) -> None:
        """Deja disponible el sprint 1 del módulo 1 al registrarse (05 §1)."""
        from sqlalchemy import text
        from app.modelos.enums import EstadoProgreso

        resultado = await self._s.execute(
            text("SELECT id FROM sprints WHERE modulo_id = 1 AND orden = 1 LIMIT 1")
        )
        fila = resultado.fetchone()
        if fila is None:
            return

        sprint_id: int = fila[0]
        progreso = ProgresoSprint(
            usuario_id=usuario_id,
            sprint_id=sprint_id,
            estado=EstadoProgreso.disponible,
        )
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(ProgresoSprint)
            .values(
                usuario_id=usuario_id,
                sprint_id=sprint_id,
                estado=EstadoProgreso.disponible,
                estrellas=0,
                mejor_aciertos=0,
                perfecto=False,
            )
            .on_conflict_do_nothing()
        )
        await self._s.execute(stmt)

    async def buscar_dispositivo_por_token(self, token: str) -> DispositivoPush | None:
        resultado = await self._s.execute(
            select(DispositivoPush).where(DispositivoPush.token == token)
        )
        return resultado.scalar_one_or_none()

    async def crear_o_reactivar_dispositivo(
        self,
        usuario_id: uuid.UUID,
        plataforma: str,
        token: str,
        ahora: datetime,
    ) -> DispositivoPush:
        existente = await self.buscar_dispositivo_por_token(token)
        if existente is not None:
            existente.activo = True
            existente.actualizado_en = ahora
            return existente

        dispositivo = DispositivoPush(
            id=uuid.uuid4(),
            usuario_id=usuario_id,
            plataforma=plataforma,
            token=token,
            activo=True,
            actualizado_en=ahora,
        )
        self._s.add(dispositivo)
        return dispositivo

    async def listar_movimientos(
        self,
        usuario_id: uuid.UUID,
        pagina: int = 1,
        por_pagina: int = 20,
    ) -> tuple[list[MovimientoEconomia], int]:
        from app.modelos.economia import MovimientoEconomia as ME

        offset = (pagina - 1) * por_pagina
        q_items = (
            select(ME)
            .where(ME.usuario_id == usuario_id)
            .order_by(ME.creado_en.desc())
            .offset(offset)
            .limit(por_pagina)
        )
        q_total = select(func.count()).select_from(ME).where(ME.usuario_id == usuario_id)

        items_res = await self._s.execute(q_items)
        total_res = await self._s.execute(q_total)

        return list(items_res.scalars()), total_res.scalar_one()

    async def listar_insignias_todas(self) -> list[Insignia]:
        res = await self._s.execute(select(Insignia))
        return list(res.scalars())

    async def listar_insignias_usuario(self, usuario_id: uuid.UUID) -> list[UsuarioInsignia]:
        res = await self._s.execute(
            select(UsuarioInsignia).where(UsuarioInsignia.usuario_id == usuario_id)
        )
        return list(res.scalars())

    async def listar_certificados(self, usuario_id: uuid.UUID) -> list[Certificado]:
        from sqlalchemy.orm import joinedload
        from app.modelos.contenido import Modulo

        res = await self._s.execute(
            select(Certificado)
            .options(
                selectinload(Certificado.modulo),
                selectinload(Certificado.usuario),
            )
            .where(Certificado.usuario_id == usuario_id)
        )
        return list(res.scalars())

    async def listar_consentimientos(self, usuario_id: uuid.UUID) -> list[Consentimiento]:
        res = await self._s.execute(
            select(Consentimiento).where(Consentimiento.usuario_id == usuario_id)
        )
        return list(res.scalars())

    async def listar_dispositivos(self, usuario_id: uuid.UUID) -> list[DispositivoPush]:
        res = await self._s.execute(
            select(DispositivoPush).where(DispositivoPush.usuario_id == usuario_id)
        )
        return list(res.scalars())
