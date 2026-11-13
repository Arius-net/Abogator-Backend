from __future__ import annotations

import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errores import NoEncontrado
from app.dominios.contenido.repositorio import ContenidoRepositorio
from app.esquemas.admin import (
    ModuloProgresoRespuesta,
    SprintIntroRespuesta,
    SprintRespuesta,
)
from app.modelos.enums import EstadoProgreso


class ContenidoServicio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion
        self._repo = ContenidoRepositorio(sesion)

    async def listar_modulos_con_progreso(
        self, usuario_id: uuid.UUID
    ) -> list[ModuloProgresoRespuesta]:
        modulos = await self._repo.listar_modulos()
        progresos = await self._repo.listar_todos_progresos_usuario(usuario_id)
        progreso_map = {p.sprint_id: p for p in progresos}

        resultado: list[ModuloProgresoRespuesta] = []
        for mod in modulos:
            sprints = await self._repo.listar_sprints_de_modulo(mod.id)
            total_sprints = len(sprints)
            completados = 0
            examen_aprobado = False

            for s in sprints:
                p = progreso_map.get(s.id)
                if p and p.estado == EstadoProgreso.completado:
                    completados += 1
                    if s.es_examen:
                        examen_aprobado = True

            resultado.append(
                ModuloProgresoRespuesta(
                    id=mod.id,
                    numero=mod.numero,
                    titulo=mod.titulo,
                    etapa_startup=mod.etapa_startup,
                    color_token=mod.color_token,
                    activo=mod.activo,
                    sprints_completados=completados,
                    total_sprints=total_sprints,
                    examen_aprobado=examen_aprobado,
                )
            )
        return resultado

    async def listar_sprints_de_modulo(
        self, usuario_id: uuid.UUID, modulo_id: int
    ) -> list[SprintRespuesta]:
        modulo = await self._repo.buscar_modulo_por_id(modulo_id)
        if modulo is None:
            raise NoEncontrado()

        sprints = await self._repo.listar_sprints_de_modulo(modulo_id)
        progresos = await self._repo.listar_progresos_usuario_modulo(usuario_id, modulo_id)
        progreso_map = {p.sprint_id: p for p in progresos}

        resultado: list[SprintRespuesta] = []
        for s in sprints:
            p = progreso_map.get(s.id)
            estado_val = p.estado.value if p else EstadoProgreso.bloqueado.value
            estrellas_val = p.estrellas if p else 0
            mejor_aciertos_val = p.mejor_aciertos if p else 0
            perfecto_val = p.perfecto if p else False

            resultado.append(
                SprintRespuesta(
                    id=s.id,
                    modulo_id=s.modulo_id,
                    orden=s.orden,
                    es_examen=s.es_examen,
                    titulo=s.titulo,
                    objetivo=s.objetivo,
                    estado=estado_val,
                    estrellas=estrellas_val,
                    mejor_aciertos=mejor_aciertos_val,
                    perfecto=perfecto_val,
                )
            )
        return resultado

    async def detalle_sprint(self, sprint_id: int) -> SprintIntroRespuesta:
        sprint = await self._repo.buscar_sprint_por_id(sprint_id)
        if sprint is None:
            raise NoEncontrado()

        return SprintIntroRespuesta(
            id=sprint.id,
            modulo_id=sprint.modulo_id,
            orden=sprint.orden,
            es_examen=sprint.es_examen,
            titulo=sprint.titulo,
            objetivo=sprint.objetivo,
            ini_presupuesto=sprint.ini_presupuesto,
            ini_reputacion=sprint.ini_reputacion,
            ini_velocidad=sprint.ini_velocidad,
            ini_riesgo=sprint.ini_riesgo,
            monedas_max=sprint.monedas_max,
        )
