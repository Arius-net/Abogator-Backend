from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS folio_certificado_seq START 1")

    meta = sa.MetaData()
    modulos_t = sa.Table(
        "modulos",
        meta,
        sa.Column("id", sa.SmallInteger, primary_key=True),
        sa.Column("numero", sa.SmallInteger),
        sa.Column("titulo", sa.String),
        sa.Column("etapa_startup", sa.String),
        sa.Column("color_token", sa.String),
        sa.Column("activo", sa.Boolean),
    )
    sprints_t = sa.Table(
        "sprints",
        meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("modulo_id", sa.SmallInteger),
        sa.Column("orden", sa.SmallInteger),
        sa.Column("es_examen", sa.Boolean),
        sa.Column("titulo", sa.String),
        sa.Column("objetivo", sa.Text),
        sa.Column("ini_presupuesto", sa.SmallInteger),
        sa.Column("ini_reputacion", sa.SmallInteger),
        sa.Column("ini_velocidad", sa.SmallInteger),
        sa.Column("ini_riesgo", sa.SmallInteger),
        sa.Column("monedas_max", sa.SmallInteger),
        sa.Column("escenario_jefe", postgresql.JSONB(none_as_null=True)),
    )
    tipo_comodin_enum = postgresql.ENUM(
        "lupa", "abogado", "amparo", "congelar_racha", name="tipo_comodin", create_type=False
    )
    comodines_t = sa.Table(
        "comodines",
        meta,
        sa.Column("id", sa.SmallInteger, primary_key=True, autoincrement=True),
        sa.Column("clave", tipo_comodin_enum, nullable=False, unique=True),
        sa.Column("nombre", sa.String),
        sa.Column("descripcion", sa.Text),
        sa.Column("precio", sa.Integer),
        sa.Column("permitido_en_examen", sa.Boolean),
        sa.Column("activo", sa.Boolean),
    )
    insignias_t = sa.Table(
        "insignias",
        meta,
        sa.Column("id", sa.SmallInteger, primary_key=True, autoincrement=True),
        sa.Column("clave", sa.String, nullable=False, unique=True),
        sa.Column("nombre", sa.String),
        sa.Column("descripcion", sa.Text),
        sa.Column("icono", sa.String),
    )

    op.bulk_insert(
        modulos_t,
        [
            {
                "id": 1,
                "numero": 1,
                "titulo": "Protección de datos",
                "etapa_startup": "Del Garage al MVP",
                "color_token": "modulo-1",
                "activo": True,
            },
            {
                "id": 2,
                "numero": 2,
                "titulo": "Licencias Open Source",
                "etapa_startup": "Ronda Semilla",
                "color_token": "modulo-2",
                "activo": True,
            },
            {
                "id": 3,
                "numero": 3,
                "titulo": "Delitos informáticos",
                "etapa_startup": "Escalando el equipo",
                "color_token": "modulo-3",
                "activo": True,
            },
            {
                "id": 4,
                "numero": 4,
                "titulo": "Contratos digitales",
                "etapa_startup": "Serie A",
                "color_token": "modulo-4",
                "activo": True,
            },
        ],
    )

    sprints_datos = []
    sprint_id = 1
    for mod_id in range(1, 5):
        for ord_sprint in range(1, 6):
            sprints_datos.append(
                {
                    "id": sprint_id,
                    "modulo_id": mod_id,
                    "orden": ord_sprint,
                    "es_examen": False,
                    "titulo": f"Módulo {mod_id} · Sprint {ord_sprint}",
                    "objetivo": f"Aprende los fundamentos del sprint {ord_sprint} del módulo {mod_id}.",
                    "ini_presupuesto": 70,
                    "ini_reputacion": 60,
                    "ini_velocidad": 50,
                    "ini_riesgo": 25,
                    "monedas_max": 60,
                }
            )
            sprint_id += 1
        sprints_datos.append(
            {
                "id": sprint_id,
                "modulo_id": mod_id,
                "orden": 6,
                "es_examen": True,
                "titulo": f"Examen Final · Módulo {mod_id}",
                "objetivo": f"Defiende tus decisiones ante el jefe de crisis del módulo {mod_id}.",
                "ini_presupuesto": 70,
                "ini_reputacion": 60,
                "ini_velocidad": 50,
                "ini_riesgo": 25,
                "monedas_max": 60,
            }
        )
        sprint_id += 1

    op.bulk_insert(sprints_t, sprints_datos)

    op.bulk_insert(
        comodines_t,
        [
            {
                "clave": "lupa",
                "nombre": "Lupa de Auditor",
                "descripcion": "Lupa — resalta las palabras trampa de la tarjeta",
                "precio": 60,
                "permitido_en_examen": False,
                "activo": True,
            },
            {
                "clave": "abogado",
                "nombre": "Abogado Senior",
                "descripcion": "Abogado — muestra el artículo o licencia exacta del caso",
                "precio": 90,
                "permitido_en_examen": False,
                "activo": True,
            },
            {
                "clave": "amparo",
                "nombre": "Amparo / Fianza",
                "descripcion": "Amparo — el siguiente error no quita vida",
                "precio": 120,
                "permitido_en_examen": False,
                "activo": True,
            },
            {
                "clave": "congelar_racha",
                "nombre": "Congelar racha",
                "descripcion": "Congelar racha — conserva la racha un día sin jugar",
                "precio": 100,
                "permitido_en_examen": False,
                "activo": True,
            },
        ],
    )

    op.bulk_insert(
        insignias_t,
        [
            {
                "clave": "primer_sprint",
                "nombre": "Primer sprint",
                "descripcion": "Completar su primer sprint",
                "icono": "primer_sprint",
            },
            {
                "clave": "racha_7",
                "nombre": "Racha de 7 días",
                "descripcion": "Llegar a racha_actual >= 7",
                "icono": "racha_7",
            },
            {
                "clave": "sprint_perfecto",
                "nombre": "Sprint perfecto",
                "descripcion": "Completar un sprint con 3 estrellas",
                "icono": "sprint_perfecto",
            },
            {
                "clave": "modulo_aprobado",
                "nombre": "Módulo aprobado",
                "descripcion": "Aprobar un Examen Final",
                "icono": "modulo_aprobado",
            },
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM insignias")
    op.execute("DELETE FROM comodines")
    op.execute("DELETE FROM sprints")
    op.execute("DELETE FROM modulos")
    op.execute("DROP SEQUENCE IF EXISTS folio_certificado_seq")
