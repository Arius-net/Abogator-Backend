from __future__ import annotations

import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errores import NoEncontrado, SaldoInsuficiente
from app.dominios.tienda.repositorio import TiendaRepositorio
from app.esquemas.jsonb import Inventario
from app.esquemas.tienda import ComodinTiendaRespuesta, CompraRespuesta, ComprarComodinInput
from app.modelos.economia import MovimientoEconomia
from app.modelos.enums import EstadoCuenta


class TiendaServicio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion
        self._repo = TiendaRepositorio(sesion)

    async def listar_catalogo(self) -> list[ComodinTiendaRespuesta]:
        comodines = await self._repo.listar_comodines_activos()
        return [
            ComodinTiendaRespuesta(
                clave=c.clave.value if hasattr(c.clave, "value") else str(c.clave),
                nombre=c.nombre,
                descripcion=c.descripcion,
                precio=c.precio,
                permitido_en_examen=c.permitido_en_examen,
            )
            for c in comodines
        ]

    async def comprar_comodin(
        self, usuario_id: uuid.UUID, datos: ComprarComodinInput
    ) -> CompraRespuesta:
        usuario = await self._repo.buscar_usuario_con_lock(usuario_id)
        if usuario is None or usuario.estado_cuenta != EstadoCuenta.activo:
            raise NoEncontrado()

        comodin = await self._repo.buscar_comodin_por_clave(datos.comodin)
        if comodin is None or not comodin.activo:
            raise NoEncontrado()

        total = comodin.precio * datos.cantidad
        if usuario.monedas < total:
            raise SaldoInsuficiente(
                detalle={"monedas_actuales": usuario.monedas, "total_requerido": total}
            )

        usuario.monedas -= total

        inv = Inventario.model_validate(usuario.inventario)
        cant_actual = getattr(inv, datos.comodin)
        setattr(inv, datos.comodin, cant_actual + datos.cantidad)
        usuario.inventario = inv.model_dump()

        await self._repo.crear_movimiento_economia(
            MovimientoEconomia(
                usuario_id=usuario_id,
                recurso="monedas",
                cantidad=-total,
                saldo_resultante=usuario.monedas,
                motivo="compra",
                detalle={
                    "comodin": datos.comodin,
                    "cantidad_comprada": datos.cantidad,
                    "precio_unitario": comodin.precio,
                },
                referencia_id=None,
            )
        )

        await self._s.commit()
        return CompraRespuesta(monedas=usuario.monedas, inventario=inv)
