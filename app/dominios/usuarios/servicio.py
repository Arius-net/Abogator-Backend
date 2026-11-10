from __future__ import annotations

import uuid
from datetime import timedelta
from math import floor

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_config
from app.core.errores import NoAutenticado, NoEncontrado
from app.core.reloj import now
from app.dominios.usuarios.repositorio import UsuariosRepositorio
from app.esquemas.jsonb import Inventario, Preferencias, RetoDiario
from app.esquemas.usuario import (
    ActualizarCuentaInput,
    CertificadoRespuesta,
    DatosPersonalesRespuesta,
    DispositivoRespuesta,
    EstadoRespuesta,
    InsigniaRespuesta,
    InventarioRespuesta,
    MovimientoRespuesta,
    MovimientosPaginados,
    PerfilRespuesta,
    ProgresoModuloRespuesta,
    RetoRespuesta,
    UsuarioRespuesta,
)
from app.modelos.enums import EstadoCuenta


class UsuariosServicio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion
        self._repo = UsuariosRepositorio(sesion)


    async def obtener_usuario(self, usuario_id: uuid.UUID) -> UsuarioRespuesta:
        usuario = await self._repo.buscar_por_id(usuario_id)
        if usuario is None:
            raise NoEncontrado()
        return UsuarioRespuesta.model_validate(usuario)

    async def actualizar_cuenta(
        self, usuario_id: uuid.UUID, datos: ActualizarCuentaInput
    ) -> UsuarioRespuesta:
        usuario = await self._repo.buscar_por_id(usuario_id)
        if usuario is None:
            raise NoEncontrado()

        if datos.nombre is not None:
            usuario.nombre = datos.nombre
        if datos.perfil is not None:
            from app.modelos.enums import PerfilUsuario
            usuario.perfil = PerfilUsuario(datos.perfil)
        if datos.zona_horaria is not None:
            usuario.zona_horaria = datos.zona_horaria

        await self._s.commit()
        await self._s.refresh(usuario)
        return UsuarioRespuesta.model_validate(usuario)


    async def estado_usuario(self, usuario_id: uuid.UUID) -> EstadoRespuesta:
        """Calcula lazy regen de vidas (05 §5) sin escribir a BD."""
        cfg = get_config()
        usuario = await self._repo.buscar_por_id(usuario_id)
        if usuario is None:
            raise NoEncontrado()

        ahora = now()
        delta_s = (ahora - usuario.vidas_base_en).total_seconds()
        regeneradas = int(delta_s // cfg.VIDA_REGEN_SEGUNDOS)
        vidas_efectivas = min(cfg.VIDAS_MAX, usuario.vidas + regeneradas)

        proxima_vida_en = None
        if vidas_efectivas < cfg.VIDAS_MAX:
            residuo_s = delta_s % cfg.VIDA_REGEN_SEGUNDOS
            proxima_vida_en = ahora + timedelta(
                seconds=cfg.VIDA_REGEN_SEGUNDOS - residuo_s
            )

        return EstadoRespuesta(
            vidas=vidas_efectivas,
            vidas_max=cfg.VIDAS_MAX,
            proxima_vida_en=proxima_vida_en,
            monedas=usuario.monedas,
            xp=usuario.xp,
            nivel=usuario.nivel,
            racha_actual=usuario.racha_actual,
            amparo_activo=usuario.amparo_activo,
        )


    async def guardar_preferencias(
        self, usuario_id: uuid.UUID, prefs: Preferencias
    ) -> Preferencias:
        usuario = await self._repo.buscar_con_lock(usuario_id)
        if usuario is None:
            raise NoEncontrado()
        usuario.preferencias = prefs.model_dump()
        await self._s.commit()
        return prefs


    async def registrar_dispositivo(
        self, usuario_id: uuid.UUID, plataforma: str, token: str
    ) -> DispositivoRespuesta:
        ahora = now()
        dispositivo = await self._repo.crear_o_reactivar_dispositivo(
            usuario_id=usuario_id,
            plataforma=plataforma,
            token=token,
            ahora=ahora,
        )
        await self._s.commit()
        await self._s.refresh(dispositivo)
        return DispositivoRespuesta(
            id=dispositivo.id,
            plataforma=dispositivo.plataforma,
            activo=dispositivo.activo,
        )


    async def exportar_datos(self, usuario_id: uuid.UUID) -> DatosPersonalesRespuesta:
        usuario = await self._repo.buscar_por_id(usuario_id)
        if usuario is None:
            raise NoEncontrado()

        consentimientos = await self._repo.listar_consentimientos(usuario_id)
        dispositivos = await self._repo.listar_dispositivos(usuario_id)

        return DatosPersonalesRespuesta(
            id=usuario.id,
            nombre=usuario.nombre,
            correo=usuario.correo,
            perfil=usuario.perfil.value,
            zona_horaria=usuario.zona_horaria,
            creado_en=usuario.creado_en,
            consentimientos=[
                {
                    "documento": c.documento,
                    "version": c.version,
                    "aceptado_en": c.aceptado_en.isoformat(),
                    "ip": str(c.ip) if c.ip is not None else None,
                }
                for c in consentimientos
            ],
            dispositivos_push=[
                {
                    "id": str(d.id),
                    "plataforma": d.plataforma,
                    "activo": d.activo,
                    "actualizado_en": d.actualizado_en.isoformat(),
                }
                for d in dispositivos
            ],
        )


    async def solicitar_borrado(self, usuario_id: uuid.UUID) -> None:
        """
        Marca la cuenta como pendiente_borrado y revoca todas las sesiones.
        RG6: nunca DELETE FROM usuarios.
        """
        from app.dominios.auth.repositorio import AuthRepositorio

        ahora = now()
        usuario = await self._repo.buscar_con_lock(usuario_id)
        if usuario is None:
            raise NoEncontrado()

        usuario.estado_cuenta = EstadoCuenta.pendiente_borrado
        usuario.eliminado_en = ahora  # type: ignore[assignment]

        auth_repo = AuthRepositorio(self._s)
        await auth_repo.revocar_todas_sesiones_usuario(usuario_id, ahora)
        await self._s.commit()


    async def inventario_usuario(self, usuario_id: uuid.UUID) -> InventarioRespuesta:
        usuario = await self._repo.buscar_por_id(usuario_id)
        if usuario is None:
            raise NoEncontrado()
        inv = Inventario.model_validate(usuario.inventario)
        return InventarioRespuesta(inventario=inv)


    async def listar_movimientos(
        self, usuario_id: uuid.UUID, pagina: int, por_pagina: int
    ) -> MovimientosPaginados:
        items, total = await self._repo.listar_movimientos(
            usuario_id, pagina, por_pagina
        )
        return MovimientosPaginados(
            items=[
                MovimientoRespuesta(
                    id=m.id,
                    recurso=m.recurso.value,
                    cantidad=m.cantidad,
                    saldo_resultante=m.saldo_resultante,
                    motivo=m.motivo,
                    detalle=m.detalle,
                    creado_en=m.creado_en,
                )
                for m in items
            ],
            total=total,
            pagina=pagina,
            por_pagina=por_pagina,
        )


    async def perfil_estadisticas(self, usuario_id: uuid.UUID) -> PerfilRespuesta:
        """
        Calcula estadísticas de perfil a partir de intentos y progreso.
        SUPUESTO: precisión global = aciertos/total de respuestas de este usuario.
        SUPUESTO: progreso_modulos se omite hasta que existan datos de módulos (Fase 2).
        """
        from sqlalchemy import func, select

        from app.modelos.juego import Intento, ProgresoSprint
        from app.modelos.contenido import Sprint, Modulo

        usuario = await self._repo.buscar_por_id(usuario_id)
        if usuario is None:
            raise NoEncontrado()

        q_sum = (
            select(
                func.coalesce(func.sum(Intento.aciertos), 0),
                func.coalesce(func.sum(Intento.aciertos + Intento.parciales + Intento.errores), 0),
            )
            .where(Intento.usuario_id == usuario_id)
        )
        res_sum = await self._s.execute(q_sum)
        aciertos_int, total_int = res_sum.one()
        precision = (aciertos_int / total_int * 100.0) if total_int > 0 else 0.0

        q_perfectos = (
            select(func.count())
            .select_from(ProgresoSprint)
            .where(
                ProgresoSprint.usuario_id == usuario_id,
                ProgresoSprint.perfecto == True,  # noqa: E712
            )
        )
        perfectos_res = await self._s.execute(q_perfectos)
        sprints_perfectos = perfectos_res.scalar_one()

        return PerfilRespuesta(
            precision_global=round(precision, 2),
            racha_actual=usuario.racha_actual,
            racha_maxima=usuario.racha_maxima,
            sprints_perfectos=sprints_perfectos,
            progreso_modulos=[],
        )


    async def listar_insignias(self, usuario_id: uuid.UUID) -> list[InsigniaRespuesta]:
        todas = await self._repo.listar_insignias_todas()
        obtenidas = await self._repo.listar_insignias_usuario(usuario_id)
        obtenidas_map = {ui.insignia_id: ui for ui in obtenidas}

        result = []
        for insignia in todas:
            ui = obtenidas_map.get(insignia.id)
            result.append(
                InsigniaRespuesta(
                    clave=insignia.clave,
                    nombre=insignia.nombre,
                    descripcion=insignia.descripcion,
                    icono=insignia.icono,
                    obtenida=ui is not None,
                    obtenida_en=ui.obtenida_en if ui is not None else None,
                )
            )
        return result


    async def listar_certificados(
        self, usuario_id: uuid.UUID
    ) -> list[CertificadoRespuesta]:
        certs = await self._repo.listar_certificados(usuario_id)
        result = []
        for cert in certs:
            result.append(
                CertificadoRespuesta(
                    folio=cert.folio,
                    modulo_numero=cert.modulo.numero,
                    modulo_titulo=cert.modulo.titulo,
                    emitido_en=cert.emitido_en,
                    nombre_usuario=cert.usuario.nombre,
                )
            )
        return result


    async def reto_hoy(self, usuario_id: uuid.UUID) -> RetoRespuesta:
        """
        Asignación lazy del reto diario (05 §9).
        Si la fecha del reto almacenado != hoy (en zona del usuario), reasigna.
        """
        import zoneinfo

        cfg = get_config()
        usuario = await self._repo.buscar_con_lock(usuario_id)
        if usuario is None:
            raise NoEncontrado()

        ahora = now()
        try:
            tz = zoneinfo.ZoneInfo(usuario.zona_horaria)
        except zoneinfo.ZoneInfoNotFoundError:
            tz = zoneinfo.ZoneInfo("UTC")

        hoy = ahora.astimezone(tz).date()
        reto_actual = RetoDiario.model_validate(usuario.reto_diario)

        if reto_actual.fecha_reto != hoy:
            reto_actual = RetoDiario.de_hoy(hoy)
            usuario.reto_diario = reto_actual.model_dump(mode="json")
            await self._s.commit()

        return RetoRespuesta(
            fecha_reto=reto_actual.fecha_reto,
            tipo=reto_actual.tipo,
            descripcion=reto_actual.descripcion,
            meta=reto_actual.meta,
            avance=reto_actual.avance,
            completado=reto_actual.completado,
            recompensa_monedas=reto_actual.recompensa_monedas,
        )
