from __future__ import annotations

import uuid
from typing import Any
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modelos.apelaciones import Apelacion
from app.modelos.contenido import Modulo, Sprint, Tarjeta
from app.modelos.economia import MovimientoEconomia
from app.modelos.enums import EstadoIntento, EstadoProgreso, TipoTarjeta
from app.modelos.juego import Intento, ProgresoSprint, Respuesta
from app.modelos.logros import Certificado, Insignia, UsuarioInsignia
from app.modelos.usuarios import Usuario


class JuegoRepositorio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def buscar_usuario_con_lock(self, usuario_id: uuid.UUID) -> Usuario | None:
        res = await self._s.execute(
            select(Usuario).where(Usuario.id == usuario_id).with_for_update()
        )
        return res.scalar_one_or_none()

    async def buscar_sprint(self, sprint_id: int) -> Sprint | None:
        return await self._s.get(Sprint, sprint_id)

    async def buscar_progreso(self, usuario_id: uuid.UUID, sprint_id: int) -> ProgresoSprint | None:
        res = await self._s.execute(
            select(ProgresoSprint).where(
                ProgresoSprint.usuario_id == usuario_id,
                ProgresoSprint.sprint_id == sprint_id,
            )
        )
        return res.scalar_one_or_none()

    async def desbloquear_siguiente_sprint(
        self, usuario_id: uuid.UUID, modulo_id: int, siguiente_orden: int
    ) -> None:
        res = await self._s.execute(
            select(Sprint).where(
                Sprint.modulo_id == modulo_id,
                Sprint.orden == siguiente_orden,
            )
        )
        sig = res.scalar_one_or_none()
        if sig is None:
            return

        stmt = (
            pg_insert(ProgresoSprint)
            .values(
                usuario_id=usuario_id,
                sprint_id=sig.id,
                estado=EstadoProgreso.disponible,
                estrellas=0,
                mejor_aciertos=0,
                perfecto=False,
            )
            .on_conflict_do_nothing()
        )
        await self._s.execute(stmt)

    async def buscar_intento_en_curso(self, usuario_id: uuid.UUID) -> Intento | None:
        res = await self._s.execute(
            select(Intento).where(
                Intento.usuario_id == usuario_id,
                Intento.estado == EstadoIntento.en_curso,
            )
        )
        return res.scalar_one_or_none()

    async def buscar_intento_por_id(self, intento_id: uuid.UUID) -> Intento | None:
        return await self._s.get(Intento, intento_id)

    async def buscar_intento_por_id_con_lock(self, intento_id: uuid.UUID) -> Intento | None:
        res = await self._s.execute(
            select(Intento).where(Intento.id == intento_id).with_for_update()
        )
        return res.scalar_one_or_none()

    async def crear_intento(self, intento: Intento) -> Intento:
        self._s.add(intento)
        return intento

    async def buscar_tarjetas_activas_sprint(self, sprint_id: int) -> list[Tarjeta]:
        res = await self._s.execute(
            select(Tarjeta).where(
                Tarjeta.sprint_id == sprint_id,
                Tarjeta.activa == True,
            )
        )
        return list(res.scalars())

    async def obtener_tarjetas_ultimos_intentos(
        self, usuario_id: uuid.UUID, sprint_id: int, limite: int = 2
    ) -> set[uuid.UUID]:
        res = await self._s.execute(
            select(Intento)
            .where(
                Intento.usuario_id == usuario_id,
                Intento.sprint_id == sprint_id,
            )
            .order_by(Intento.iniciado_en.desc())
            .limit(limite)
        )
        vistas: set[uuid.UUID] = set()
        for intento in res.scalars():
            if isinstance(intento.tarjetas_asignadas, list):
                for t in intento.tarjetas_asignadas:
                    tid = t.get("tarjeta_id")
                    if tid:
                        vistas.add(uuid.UUID(str(tid)))
        return vistas

    async def buscar_tarjeta_version(self, tarjeta_id: uuid.UUID, version: int) -> Tarjeta | None:
        res = await self._s.execute(
            select(Tarjeta).where(
                Tarjeta.id == tarjeta_id,
                Tarjeta.version == version,
            )
        )
        return res.scalar_one_or_none()

    async def buscar_respuesta_por_id(self, respuesta_id: uuid.UUID) -> Respuesta | None:
        return await self._s.get(Respuesta, respuesta_id)

    async def buscar_respuesta_por_tarjeta(
        self, intento_id: uuid.UUID, tarjeta_id: uuid.UUID
    ) -> Respuesta | None:
        res = await self._s.execute(
            select(Respuesta).where(
                Respuesta.intento_id == intento_id,
                Respuesta.tarjeta_id == tarjeta_id,
            )
        )
        return res.scalar_one_or_none()

    async def crear_respuesta(self, respuesta: Respuesta) -> Respuesta:
        self._s.add(respuesta)
        return respuesta

    async def crear_movimiento_economia(self, mov: MovimientoEconomia) -> None:
        self._s.add(mov)

    async def buscar_apelacion_pendiente(
        self, usuario_id: uuid.UUID, tarjeta_id: uuid.UUID
    ) -> Apelacion | None:
        from app.modelos.enums import EstadoApelacion

        res = await self._s.execute(
            select(Apelacion).where(
                Apelacion.usuario_id == usuario_id,
                Apelacion.tarjeta_id == tarjeta_id,
                Apelacion.estado == EstadoApelacion.pendiente,
            )
        )
        return res.scalar_one_or_none()

    async def crear_apelacion(self, apelacion: Apelacion) -> None:
        self._s.add(apelacion)

    async def contar_respuestas_intento(self, intento_id: uuid.UUID) -> int:
        res = await self._s.execute(
            select(func.count()).select_from(Respuesta).where(Respuesta.intento_id == intento_id)
        )
        return res.scalar_one()

    async def listar_respuestas_intento(self, intento_id: uuid.UUID) -> list[Respuesta]:
        res = await self._s.execute(select(Respuesta).where(Respuesta.intento_id == intento_id))
        return list(res.scalars())

    async def otorgar_insignia(self, usuario_id: uuid.UUID, clave: str) -> bool:
        res_ins = await self._s.execute(select(Insignia.id).where(Insignia.clave == clave))
        ins_id = res_ins.scalar_one_or_none()
        if ins_id is None:
            return False
        stmt = (
            pg_insert(UsuarioInsignia)
            .values(
                usuario_id=usuario_id,
                insignia_id=ins_id,
            )
            .on_conflict_do_nothing()
        )
        res = await self._s.execute(stmt)
        return bool(res.rowcount and res.rowcount > 0)

    async def buscar_modulo(self, modulo_id: int) -> Modulo | None:
        return await self._s.get(Modulo, modulo_id)

    async def contar_sprints_completados_modulo(self, usuario_id: uuid.UUID, modulo_id: int) -> int:
        res = await self._s.execute(
            select(func.count())
            .select_from(ProgresoSprint)
            .join(Sprint, Sprint.id == ProgresoSprint.sprint_id)
            .where(
                ProgresoSprint.usuario_id == usuario_id,
                Sprint.modulo_id == modulo_id,
                Sprint.es_examen == False,
                ProgresoSprint.estado == EstadoProgreso.completado,
            )
        )
        return res.scalar_one()

    async def buscar_certificado(self, usuario_id: uuid.UUID, modulo_id: int) -> Certificado | None:
        res = await self._s.execute(
            select(Certificado).where(
                Certificado.usuario_id == usuario_id,
                Certificado.modulo_id == modulo_id,
            )
        )
        return res.scalar_one_or_none()

    async def crear_certificado(self, certificado: Certificado) -> None:
        self._s.add(certificado)

    async def obtener_siguiente_folio_seq(self) -> int:
        res = await self._s.execute(text("SELECT nextval('folio_certificado_seq')"))
        return int(res.scalar_one())

    async def desbloquear_siguiente_modulo(
        self, usuario_id: uuid.UUID, modulo_numero_siguiente: int
    ) -> None:
        res = await self._s.execute(select(Modulo).where(Modulo.numero == modulo_numero_siguiente))
        mod_sig = res.scalar_one_or_none()
        if mod_sig is None:
            return

        res_sprint = await self._s.execute(
            select(Sprint).where(Sprint.modulo_id == mod_sig.id, Sprint.orden == 1)
        )
        sprint_1 = res_sprint.scalar_one_or_none()
        if sprint_1 is None:
            return

        stmt = (
            pg_insert(ProgresoSprint)
            .values(
                usuario_id=usuario_id,
                sprint_id=sprint_1.id,
                estado=EstadoProgreso.disponible,
                estrellas=0,
                mejor_aciertos=0,
                perfecto=False,
            )
            .on_conflict_do_nothing()
        )
        await self._s.execute(stmt)
