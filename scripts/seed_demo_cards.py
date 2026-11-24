from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_config
from app.modelos.contenido import Sprint, Tarjeta
from app.modelos.enums import TipoTarjeta


def _crear_datos_tarjeta(sprint_id: int, tipo: TipoTarjeta, numero: int) -> dict:
    ci = {
        "veredictos": {
            "legal": {
                "resultado": "incorrecto",
                "d_presupuesto": 0,
                "d_reputacion": -5,
                "d_velocidad": 10,
                "d_riesgo": 25,
            },
            "ilegal": {
                "resultado": "correcto",
                "d_presupuesto": -5,
                "d_reputacion": 5,
                "d_velocidad": -10,
                "d_riesgo": -20,
            },
            "condicional": {
                "resultado": "parcial",
                "d_presupuesto": 0,
                "d_reputacion": 0,
                "d_velocidad": 0,
                "d_riesgo": 5,
            },
            "escalar": {
                "resultado": "incorrecto",
                "d_presupuesto": -10,
                "d_reputacion": 0,
                "d_velocidad": -5,
                "d_riesgo": 0,
            },
        },
        "evidencia": None,
        "micro_pregunta": {
            "tipo": "por_que",
            "enunciado": "Por que esta accion es contraria a la ley de privacidad?",
            "opciones": [
                {
                    "id": 1,
                    "texto": "Vulnera el consentimiento informado y el principio de proporcionalidad.",
                    "es_correcta": True,
                },
                {
                    "id": 2,
                    "texto": "Porque la empresa debe reducir costos de servidores.",
                    "es_correcta": False,
                },
            ],
        },
    }

    if tipo == TipoTarjeta.evidencia:
        ci["evidencia"] = {
            "requerida": True,
            "formato": "codigo",
            "nombre_archivo": "tracker.js",
            "contenido_texto": "const tracker = new Analytics();\ntracker.recordKeystrokes();\ntracker.sendData();",
            "lineas_infractoras": [2],
        }
        ci["micro_pregunta"] = {
            "tipo": "evidencia",
            "enunciado": "Que linea de codigo implementa la captura no autorizada?",
            "opciones": [
                {"id": 1, "texto": "tracker.recordKeystrokes() en linea 2", "es_correcta": True},
                {
                    "id": 2,
                    "texto": "const tracker = new Analytics() en linea 1",
                    "es_correcta": False,
                },
            ],
        }
    elif tipo == TipoTarjeta.justificacion:
        ci["micro_pregunta"] = {
            "tipo": "justificacion",
            "enunciado": "Selecciona el fundamento legal aplicable a este tratamiento de datos.",
            "opciones": [
                {"id": 1, "texto": "Articulo 16 Constitucional y LFPDPPP", "es_correcta": True},
                {"id": 2, "texto": "Codigo de Comercio Art. 89", "es_correcta": False},
            ],
        }

    return {
        "id": uuid.uuid4(),
        "version": 1,
        "sprint_id": sprint_id,
        "tipo": tipo,
        "categoria": "privacidad",
        "personaje_nombre": f"Personaje {numero}",
        "personaje_rol": "Ingeniero de Software",
        "iniciales": f"P{numero}",
        "texto": f"Situacion {numero}: Un directivo solicita registrar pulsaciones de teclado en laptops laborales sin notificar a los empleados.",
        "explicacion": "El monitoreo secreto de comunicaciones laborales viola el derecho a la intimidad y proteccion de datos personales.",
        "nota_abogado": "El consentimiento expreso es indispensable para datos sensibles.",
        "array_palabras_trampa": ["secreto", "sin notificar"],
        "contenido_interactivo": ci,
        "activa": True,
        "actualizado_en": datetime.now(timezone.utc),
    }


async def seed() -> None:
    cfg = get_config()
    engine = create_async_engine(cfg.DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as sesion:
        sesion: AsyncSession

        sprints_normales = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23]

        for sprint_id in sprints_normales:
            res = await sesion.execute(
                select(Tarjeta).where(Tarjeta.sprint_id == sprint_id, Tarjeta.activa == True)
            )
            existentes = res.scalars().all()
            normales_ok = sum(1 for t in existentes if t.tipo == TipoTarjeta.normal) >= 6
            evidencias_ok = sum(1 for t in existentes if t.tipo == TipoTarjeta.evidencia) >= 3
            just_ok = sum(1 for t in existentes if t.tipo == TipoTarjeta.justificacion) >= 1
            if normales_ok and evidencias_ok and just_ok:
                print(f"Sprint {sprint_id} ya tiene suficientes tarjetas.")
                continue

            tarjetas_a_crear = []
            normales_existentes = sum(1 for t in existentes if t.tipo == TipoTarjeta.normal)
            evidencias_existentes = sum(1 for t in existentes if t.tipo == TipoTarjeta.evidencia)
            just_existentes = sum(1 for t in existentes if t.tipo == TipoTarjeta.justificacion)

            for i in range(normales_existentes + 1, 7 + 1):
                tarjetas_a_crear.append(
                    Tarjeta(**_crear_datos_tarjeta(sprint_id, TipoTarjeta.normal, i))
                )
            for i in range(evidencias_existentes + 1, 3 + 1):
                tarjetas_a_crear.append(
                    Tarjeta(**_crear_datos_tarjeta(sprint_id, TipoTarjeta.evidencia, i + 6))
                )
            for i in range(just_existentes + 1, 1 + 1):
                tarjetas_a_crear.append(
                    Tarjeta(**_crear_datos_tarjeta(sprint_id, TipoTarjeta.justificacion, 10))
                )

            if tarjetas_a_crear:
                sesion.add_all(tarjetas_a_crear)
                await sesion.commit()
                print(f"Sprint {sprint_id}: creadas {len(tarjetas_a_crear)} tarjetas.")

        examenes = [6, 12, 18, 24]
        for examen_id in examenes:
            examen = await sesion.get(Sprint, examen_id)
            if examen and examen.escenario_jefe is None:
                escenario = {
                    "titulo": f"Crisis de Filtracion en Startup FinTech (Sprint {examen_id})",
                    "descripcion": "El sistema central ha sufrido un incidente de seguridad con riesgo de exfiltracion.",
                    "jefe": {
                        "nombre": "Lic. Rodrigo Voraz",
                        "avatar_url": "boss.png",
                        "hp_maximo": 100,
                    },
                    "decisiones": [
                        {
                            "id": "dec_1",
                            "hora_crisis": 0,
                            "situacion": "Se detectan accesos anomalos a la base de datos de usuarios.",
                            "opciones": [
                                {
                                    "id": "op_1",
                                    "texto": "Desconectar servidores afectados inmediatamente",
                                    "es_correcta": True,
                                },
                                {
                                    "id": "op_2",
                                    "texto": "Ignorar la alerta hasta el lunes",
                                    "es_correcta": False,
                                },
                            ],
                            "tiempo_segundos": 30,
                            "replica_jefe": "En que te basas para interrumpir las operaciones productivas?",
                            "contraargumentos": [
                                {
                                    "id": "fund_1",
                                    "texto": "Principio de contencion y mitigacion de dano",
                                    "es_valido": True,
                                },
                                {
                                    "id": "fund_2",
                                    "texto": "Para ahorrar consumo de energia electrica",
                                    "es_valido": False,
                                },
                            ],
                        }
                    ],
                }
                examen.escenario_jefe = escenario
                await sesion.commit()
                print(f"Cargado escenario de jefe para Sprint {examen_id} (Examen).")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
