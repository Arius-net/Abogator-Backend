from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.providers import get_push_provider
from app.core.reloj import now
from app.modelos.apelaciones import Notificacion
from app.modelos.usuarios import DispositivoPush
from worker.candado import candado_redis


async def tarea_envio_push(sesion: AsyncSession) -> int:
    async with candado_redis("tarea:envio_push", ttl_segundos=50) as adquirido:
        if not adquirido:
            return 0

        ahora = now()
        q = (
            select(Notificacion)
            .where(
                Notificacion.estado == "pendiente",
                Notificacion.programada_para <= ahora,
            )
            .order_by(Notificacion.programada_para.asc())
            .limit(100)
        )
        res = await sesion.execute(q)
        pendientes = list(res.scalars())

        if not pendientes:
            return 0

        push_provider = get_push_provider()
        enviadas_count = 0

        for notif in pendientes:
            q_devs = select(DispositivoPush).where(
                DispositivoPush.usuario_id == notif.usuario_id,
                DispositivoPush.activo == True,
            )
            res_devs = await sesion.execute(q_devs)
            devs = list(res_devs.scalars())

            if not devs:
                notif.estado = "enviada"
                notif.enviada_en = ahora
                enviadas_count += 1
                continue

            alguna_enviada = False
            for dev in devs:
                exito = await push_provider.enviar(
                    token=dev.token,
                    plataforma=dev.plataforma,
                    titulo=notif.titulo,
                    cuerpo=notif.cuerpo,
                    datos={"referencia_id": str(notif.referencia_id)}
                    if notif.referencia_id
                    else None,
                )
                if not exito:
                    dev.activo = False
                else:
                    alguna_enviada = True

            notif.estado = "enviada" if alguna_enviada else "fallida"
            notif.enviada_en = ahora
            enviadas_count += 1

        await sesion.commit()
        return enviadas_count
