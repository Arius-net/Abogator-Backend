from __future__ import annotations

import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errores import NoEncontrado, PeticionInvalida
from app.core.reloj import now
from app.dominios.admin.repositorio import AdminRepositorio
from app.esquemas.admin import (
    ActualizarComodinInput,
    CargarEscenarioInput,
    ComodinAdminRespuesta,
    CrearTarjetaInput,
    EditarTarjetaInput,
    EstadoTarjetaInput,
    MetricasAdminRespuesta,
    ReemplazarEscenarioInput,
    TarjetaAdminRespuesta,
)
from app.esquemas.contenido import ContenidoInteractivo, EscenarioJefe
from app.modelos.contenido import Tarjeta
from app.modelos.enums import TipoTarjeta


class AdminServicio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion
        self._repo = AdminRepositorio(sesion)

    async def listar_tarjetas(
        self,
        sprint_id: int | None = None,
        tipo: str | None = None,
        activa: bool | None = None,
        version: int | None = None,
    ) -> list[TarjetaAdminRespuesta]:
        tarjetas = await self._repo.listar_tarjetas(sprint_id, tipo, activa, version)
        return [
            TarjetaAdminRespuesta(
                id=t.id,
                version=t.version,
                sprint_id=t.sprint_id,
                tipo=t.tipo.value,
                categoria=t.categoria,
                personaje_nombre=t.personaje_nombre,
                personaje_rol=t.personaje_rol,
                iniciales=t.iniciales,
                texto=t.texto,
                explicacion=t.explicacion,
                nota_abogado=t.nota_abogado,
                array_palabras_trampa=t.array_palabras_trampa,
                contenido_interactivo=t.contenido_interactivo,
                activa=t.activa,
                actualizado_en=t.actualizado_en,
            )
            for t in tarjetas
        ]

    async def crear_tarjeta(
        self, admin_id: uuid.UUID, datos: CrearTarjetaInput
    ) -> TarjetaAdminRespuesta:
        sprint = await self._repo.buscar_sprint_por_id(datos.sprint_id)
        if sprint is None:
            raise NoEncontrado()

        try:
            datos.contenido_interactivo.validar_para_tipo_tarjeta(datos.tipo)
        except ValueError as e:
            raise PeticionInvalida(detalle={"motivo": str(e)})

        tarjeta = Tarjeta(
            id=uuid.uuid4(),
            version=1,
            sprint_id=datos.sprint_id,
            tipo=TipoTarjeta(datos.tipo),
            categoria=datos.categoria,
            personaje_nombre=datos.personaje_nombre,
            personaje_rol=datos.personaje_rol,
            iniciales=datos.iniciales,
            texto=datos.texto,
            explicacion=datos.explicacion,
            nota_abogado=datos.nota_abogado,
            array_palabras_trampa=datos.array_palabras_trampa,
            contenido_interactivo=datos.contenido_interactivo.model_dump(mode="json"),
            activa=False,
            actualizado_en=now(),
        )
        await self._repo.crear_tarjeta(tarjeta)

        await self._repo.registrar_auditoria(
            admin_id=admin_id,
            accion="crear",
            entidad="tarjeta",
            entidad_id=str(tarjeta.id),
            cambios={"antes": None, "despues": {"sprint_id": datos.sprint_id, "tipo": datos.tipo}},
        )

        await self._s.commit()
        await self._s.refresh(tarjeta)

        return TarjetaAdminRespuesta(
            id=tarjeta.id,
            version=tarjeta.version,
            sprint_id=tarjeta.sprint_id,
            tipo=tarjeta.tipo.value,
            categoria=tarjeta.categoria,
            personaje_nombre=tarjeta.personaje_nombre,
            personaje_rol=tarjeta.personaje_rol,
            iniciales=tarjeta.iniciales,
            texto=tarjeta.texto,
            explicacion=tarjeta.explicacion,
            nota_abogado=tarjeta.nota_abogado,
            array_palabras_trampa=tarjeta.array_palabras_trampa,
            contenido_interactivo=tarjeta.contenido_interactivo,
            activa=tarjeta.activa,
            actualizado_en=tarjeta.actualizado_en,
        )

    async def editar_tarjeta(
        self, admin_id: uuid.UUID, tarjeta_id: uuid.UUID, datos: EditarTarjetaInput
    ) -> TarjetaAdminRespuesta:
        vieja = await self._repo.buscar_tarjeta_por_id(tarjeta_id)
        if vieja is None:
            raise NoEncontrado()

        if not vieja.activa:
            raise PeticionInvalida(
                detalle={"motivo": "Solo se puede editar la versión activa de una tarjeta."}
            )

        vieja.activa = False

        nuevo_tipo = datos.tipo or vieja.tipo.value
        nuevo_contenido_dict = (
            datos.contenido_interactivo.model_dump(mode="json")
            if datos.contenido_interactivo is not None
            else vieja.contenido_interactivo
        )

        try:
            ci = ContenidoInteractivo.model_validate(nuevo_contenido_dict)
            ci.validar_para_tipo_tarjeta(nuevo_tipo)
        except Exception as e:
            raise PeticionInvalida(detalle={"motivo": str(e)})

        nueva = Tarjeta(
            id=uuid.uuid4(),
            version=vieja.version + 1,
            sprint_id=datos.sprint_id if datos.sprint_id is not None else vieja.sprint_id,
            tipo=TipoTarjeta(nuevo_tipo),
            categoria=datos.categoria if datos.categoria is not None else vieja.categoria,
            personaje_nombre=(
                datos.personaje_nombre
                if datos.personaje_nombre is not None
                else vieja.personaje_nombre
            ),
            personaje_rol=(
                datos.personaje_rol if datos.personaje_rol is not None else vieja.personaje_rol
            ),
            iniciales=datos.iniciales if datos.iniciales is not None else vieja.iniciales,
            texto=datos.texto if datos.texto is not None else vieja.texto,
            explicacion=datos.explicacion if datos.explicacion is not None else vieja.explicacion,
            nota_abogado=(
                datos.nota_abogado if datos.nota_abogado is not None else vieja.nota_abogado
            ),
            array_palabras_trampa=(
                datos.array_palabras_trampa
                if datos.array_palabras_trampa is not None
                else vieja.array_palabras_trampa
            ),
            contenido_interactivo=nuevo_contenido_dict,
            activa=True,
            actualizado_en=now(),
        )
        await self._repo.crear_tarjeta(nueva)

        await self._repo.registrar_auditoria(
            admin_id=admin_id,
            accion="editar",
            entidad="tarjeta",
            entidad_id=str(nueva.id),
            cambios={
                "antes": {"id": str(vieja.id), "version": vieja.version},
                "despues": {"id": str(nueva.id), "version": nueva.version},
            },
        )

        await self._s.commit()
        await self._s.refresh(nueva)

        return TarjetaAdminRespuesta(
            id=nueva.id,
            version=nueva.version,
            sprint_id=nueva.sprint_id,
            tipo=nueva.tipo.value,
            categoria=nueva.categoria,
            personaje_nombre=nueva.personaje_nombre,
            personaje_rol=nueva.personaje_rol,
            iniciales=nueva.iniciales,
            texto=nueva.texto,
            explicacion=nueva.explicacion,
            nota_abogado=nueva.nota_abogado,
            array_palabras_trampa=nueva.array_palabras_trampa,
            contenido_interactivo=nueva.contenido_interactivo,
            activa=nueva.activa,
            actualizado_en=nueva.actualizado_en,
        )

    async def cambiar_estado_tarjeta(
        self, admin_id: uuid.UUID, tarjeta_id: uuid.UUID, datos: EstadoTarjetaInput
    ) -> TarjetaAdminRespuesta:
        tarjeta = await self._repo.buscar_tarjeta_por_id(tarjeta_id)
        if tarjeta is None:
            raise NoEncontrado()

        if datos.activa:
            try:
                ci = ContenidoInteractivo.model_validate(tarjeta.contenido_interactivo)
                ci.validar_para_tipo_tarjeta(tarjeta.tipo.value)
            except Exception as e:
                raise PeticionInvalida(
                    detalle={"motivo": f"Contenido interactivo no válido para activación: {e}"}
                )

        estado_anterior = tarjeta.activa
        tarjeta.activa = datos.activa

        accion_str = "activar" if datos.activa else "desactivar"
        await self._repo.registrar_auditoria(
            admin_id=admin_id,
            accion=accion_str,
            entidad="tarjeta",
            entidad_id=str(tarjeta.id),
            cambios={"antes": {"activa": estado_anterior}, "despues": {"activa": datos.activa}},
        )

        await self._s.commit()
        await self._s.refresh(tarjeta)

        return TarjetaAdminRespuesta(
            id=tarjeta.id,
            version=tarjeta.version,
            sprint_id=tarjeta.sprint_id,
            tipo=tarjeta.tipo.value,
            categoria=tarjeta.categoria,
            personaje_nombre=tarjeta.personaje_nombre,
            personaje_rol=tarjeta.personaje_rol,
            iniciales=tarjeta.iniciales,
            texto=tarjeta.texto,
            explicacion=tarjeta.explicacion,
            nota_abogado=tarjeta.nota_abogado,
            array_palabras_trampa=tarjeta.array_palabras_trampa,
            contenido_interactivo=tarjeta.contenido_interactivo,
            activa=tarjeta.activa,
            actualizado_en=tarjeta.actualizado_en,
        )

    async def cargar_escenario(
        self, admin_id: uuid.UUID, datos: CargarEscenarioInput
    ) -> dict[str, str]:
        sprint = await self._repo.buscar_sprint_por_id(datos.sprint_id)
        if sprint is None:
            raise NoEncontrado()
        if not sprint.es_examen:
            raise PeticionInvalida(
                detalle={"motivo": "Solo los sprints de examen pueden tener escenario."}
            )

        for d in datos.escenario.decisiones:
            t = await self._repo.buscar_tarjeta_por_id(d.tarjeta_id)
            if t is None:
                raise PeticionInvalida(detalle={"motivo": f"Tarjeta {d.tarjeta_id} no existe."})
            s_t = await self._repo.buscar_sprint_por_id(t.sprint_id)
            if s_t is None or s_t.modulo_id != sprint.modulo_id:
                raise PeticionInvalida(
                    detalle={"motivo": f"Tarjeta {d.tarjeta_id} no pertenece al mismo módulo."}
                )

        sprint.escenario_jefe = datos.escenario.model_dump(mode="json")

        await self._repo.registrar_auditoria(
            admin_id=admin_id,
            accion="crear",
            entidad="escenario",
            entidad_id=str(sprint.id),
            cambios={"antes": None, "despues": {"sprint_id": sprint.id}},
        )

        await self._s.commit()
        return {"mensaje": "Escenario cargado exitosamente."}

    async def reemplazar_escenario(
        self, admin_id: uuid.UUID, sprint_id: int, datos: ReemplazarEscenarioInput
    ) -> dict[str, str]:
        sprint = await self._repo.buscar_sprint_por_id(sprint_id)
        if sprint is None:
            raise NoEncontrado()
        if not sprint.es_examen:
            raise PeticionInvalida(
                detalle={"motivo": "Solo los sprints de examen pueden tener escenario."}
            )

        for d in datos.escenario.decisiones:
            t = await self._repo.buscar_tarjeta_por_id(d.tarjeta_id)
            if t is None:
                raise PeticionInvalida(detalle={"motivo": f"Tarjeta {d.tarjeta_id} no existe."})
            s_t = await self._repo.buscar_sprint_por_id(t.sprint_id)
            if s_t is None or s_t.modulo_id != sprint.modulo_id:
                raise PeticionInvalida(
                    detalle={"motivo": f"Tarjeta {d.tarjeta_id} no pertenece al mismo módulo."}
                )

        sprint.escenario_jefe = datos.escenario.model_dump(mode="json")

        await self._repo.registrar_auditoria(
            admin_id=admin_id,
            accion="reemplazar",
            entidad="escenario",
            entidad_id=str(sprint.id),
            cambios={"antes": "escenario_anterior", "despues": "nuevo_escenario"},
        )

        await self._s.commit()
        return {"mensaje": "Escenario actualizado exitosamente."}

    async def actualizar_comodin(
        self, admin_id: uuid.UUID, clave: str, datos: ActualizarComodinInput
    ) -> ComodinAdminRespuesta:
        comodin = await self._repo.buscar_comodin_por_clave(clave)
        if comodin is None:
            raise NoEncontrado()

        antes = {"precio": comodin.precio, "activo": comodin.activo}

        if datos.precio is not None:
            comodin.precio = datos.precio
        if datos.activo is not None:
            comodin.activo = datos.activo

        despues = {"precio": comodin.precio, "activo": comodin.activo}

        await self._repo.registrar_auditoria(
            admin_id=admin_id,
            accion="editar",
            entidad="comodin",
            entidad_id=clave,
            cambios={"antes": antes, "despues": despues},
        )

        await self._s.commit()
        await self._s.refresh(comodin)

        return ComodinAdminRespuesta(
            clave=comodin.clave.value if hasattr(comodin.clave, "value") else str(comodin.clave),
            nombre=comodin.nombre,
            descripcion=comodin.descripcion,
            precio=comodin.precio,
            permitido_en_examen=comodin.permitido_en_examen,
            activo=comodin.activo,
        )

    async def metricas(self) -> MetricasAdminRespuesta:
        data = await self._repo.obtener_metricas()
        return MetricasAdminRespuesta(
            tasa_acierto_tarjetas=data["tasa_acierto_tarjetas"],
            quiebras_por_sprint=data["quiebras_por_sprint"],
            retencion_apelaciones=data["retencion_apelaciones"],
        )
