from __future__ import annotations

import uuid
from typing import Any
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos.admin import AuditoriaAdmin
from app.modelos.contenido import Modulo, Sprint, Tarjeta
from app.modelos.economia import Comodin
from app.modelos.enums import EstadoIntento, ResultadoRespuesta, TipoTarjeta
from app.modelos.juego import Intento, Respuesta


class AdminRepositorio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def listar_tarjetas(
        self,
        sprint_id: int | None = None,
        tipo: str | None = None,
        activa: bool | None = None,
        version: int | None = None,
    ) -> list[Tarjeta]:
        q = select(Tarjeta)
        if sprint_id is not None:
            q = q.where(Tarjeta.sprint_id == sprint_id)
        if tipo is not None:
            q = q.where(Tarjeta.tipo == TipoTarjeta(tipo))
        if activa is not None:
            q = q.where(Tarjeta.activa == activa)
        if version is not None:
            q = q.where(Tarjeta.version == version)
        q = q.order_by(Tarjeta.sprint_id, Tarjeta.version.desc())
        res = await self._s.execute(q)
        return list(res.scalars())

    async def buscar_tarjeta_por_id(self, tarjeta_id: uuid.UUID) -> Tarjeta | None:
        return await self._s.get(Tarjeta, tarjeta_id)

    async def crear_tarjeta(self, tarjeta: Tarjeta) -> Tarjeta:
        self._s.add(tarjeta)
        return tarjeta

    async def buscar_sprint_por_id(self, sprint_id: int) -> Sprint | None:
        return await self._s.get(Sprint, sprint_id)

    async def buscar_comodin_por_clave(self, clave: str) -> Comodin | None:
        res = await self._s.execute(select(Comodin).where(Comodin.clave == clave))
        return res.scalar_one_or_none()

    async def registrar_auditoria(
        self,
        admin_id: uuid.UUID,
        accion: str,
        entidad: str,
        entidad_id: str,
        cambios: dict[str, Any],
    ) -> AuditoriaAdmin:
        auditoria = AuditoriaAdmin(
            admin_id=admin_id,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            cambios=cambios,
        )
        self._s.add(auditoria)
        return auditoria

    async def obtener_metricas(self) -> dict[str, Any]:
        q_tarjetas = (
            select(
                Respuesta.tarjeta_id,
                func.count().label("total"),
                func.sum(
                    case((Respuesta.resultado == ResultadoRespuesta.correcto, 1), else_=0)
                ).label("aciertos"),
            )
            .group_by(Respuesta.tarjeta_id)
        )
        res_t = await self._s.execute(q_tarjetas)
        tasa_tarjetas = []
        for fila in res_t.all():
            total = fila.total or 0
            aciertos = fila.aciertos or 0
            pct = round((aciertos / total * 100.0), 2) if total > 0 else 0.0
            tasa_tarjetas.append(
                {"tarjeta_id": str(fila.tarjeta_id), "total": total, "tasa_acierto": pct}
            )

        q_quiebras = (
            select(
                Intento.sprint_id,
                func.count().label("quiebras"),
            )
            .where(Intento.estado == EstadoIntento.quebrado)
            .group_by(Intento.sprint_id)
        )
        res_q = await self._s.execute(q_quiebras)
        quiebras_sprint = [
            {"sprint_id": fila.sprint_id, "quiebras": fila.quiebras}
            for fila in res_q.all()
        ]

        return {
            "tasa_acierto_tarjetas": tasa_tarjetas,
            "quiebras_por_sprint": quiebras_sprint,
            "retencion_apelaciones": {"tasa_retencion": 0.0, "total_apelaciones": 0},
        }
