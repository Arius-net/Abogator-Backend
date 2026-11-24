from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_config
from app.core.security import hashear_contrasena
from app.modelos.enums import EstadoCuenta, PerfilUsuario, RolUsuario
from app.modelos.usuarios import Usuario

PREFERENCIAS_DEFAULT = {
    "modo_oscuro": False,
    "escala_texto": 1.0,
    "etiquetas_lector": False,
    "botones_en_lugar_de_deslizar": False,
    "haptica": True,
    "tiempo_extendido": False,
    "reducir_animaciones": False,
    "notif_racha": True,
    "notif_apelaciones": True,
    "notif_vidas": True,
}
INVENTARIO_DEFAULT = {"lupa": 0, "abogado": 0, "amparo": 0, "congelar_racha": 0}


async def crear_superadmin() -> None:
    cfg = get_config()

    if not cfg.ADMIN_EMAIL or not cfg.ADMIN_PASSWORD:
        print("ERROR: Define ADMIN_EMAIL y ADMIN_PASSWORD en el entorno.", file=sys.stderr)
        sys.exit(1)

    engine = create_async_engine(cfg.DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as sesion:
        sesion: AsyncSession
        existente = await sesion.scalar(select(Usuario).where(Usuario.correo == cfg.ADMIN_EMAIL))
        if existente:
            print(f"El usuario {cfg.ADMIN_EMAIL} ya existe. Nada que hacer.")
            await engine.dispose()
            return

        from app.core.reloj import now
        import datetime

        ahora = now()
        import math

        dia_del_año = ahora.timetuple().tm_yday
        tipos = [
            "aciertos_seguidos",
            "sprints_completados",
            "por_que_correctos",
            "evidencias_inspeccionadas",
        ]
        tipo_hoy = tipos[dia_del_año % 4]
        reto_default = {
            "fecha_reto": ahora.date().isoformat(),
            "tipo": tipo_hoy,
            "descripcion": "Reto del día",
            "meta": 1,
            "avance": 0,
            "completado": False,
            "recompensa_monedas": 15,
        }

        admin = Usuario(
            id=uuid.uuid4(),
            nombre="Admin",
            correo=cfg.ADMIN_EMAIL,
            hash_contrasena=hashear_contrasena(cfg.ADMIN_PASSWORD),
            perfil=PerfilUsuario.desarrollador,
            rol=RolUsuario.admin,
            estado_cuenta=EstadoCuenta.activo,
            zona_horaria="America/Mexico_City",
            vidas=5,
            vidas_base_en=ahora,
            monedas=0,
            xp=0,
            nivel=1,
            racha_actual=0,
            racha_maxima=0,
            amparo_activo=False,
            preferencias=PREFERENCIAS_DEFAULT,
            inventario=INVENTARIO_DEFAULT,
            reto_diario=reto_default,
        )
        sesion.add(admin)
        await sesion.commit()
        print(f"Superadmin creado: {cfg.ADMIN_EMAIL} (id={admin.id})")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(crear_superadmin())
