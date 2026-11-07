"""0001 esquema inicial

Revision ID: 0001
Revises: 
Create Date: 2026-11-16

Crea:
- Extensión citext
- 11 tipos ENUM de PostgreSQL
- 20 tablas con constraints e índices de 03_base_de_datos.md
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extensiones ───────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # ── Tipos ENUM (11 tipos según 03 §1) ─────────────────────────────────────
    op.execute("""
        CREATE TYPE perfil_usuario AS ENUM ('estudiante', 'desarrollador', 'legal')
    """)
    op.execute("""
        CREATE TYPE rol_usuario AS ENUM ('jugador', 'admin')
    """)
    op.execute("""
        CREATE TYPE estado_cuenta AS ENUM ('activo', 'suspendido', 'pendiente_borrado')
    """)
    op.execute("""
        CREATE TYPE veredicto AS ENUM ('legal', 'ilegal', 'condicional', 'escalar')
    """)
    op.execute("""
        CREATE TYPE resultado_respuesta AS ENUM ('correcto', 'parcial', 'incorrecto', 'tiempo_agotado')
    """)
    op.execute("""
        CREATE TYPE tipo_tarjeta AS ENUM ('normal', 'evidencia', 'justificacion')
    """)
    op.execute("""
        CREATE TYPE tipo_intento AS ENUM ('sprint', 'examen')
    """)
    op.execute("""
        CREATE TYPE estado_intento AS ENUM ('en_curso', 'completado', 'quebrado', 'aprobado', 'reprobado', 'abandonado')
    """)
    op.execute("""
        CREATE TYPE estado_progreso AS ENUM ('bloqueado', 'disponible', 'completado')
    """)
    op.execute("""
        CREATE TYPE tipo_comodin AS ENUM ('lupa', 'abogado', 'amparo', 'congelar_racha')
    """)
    op.execute("""
        CREATE TYPE estado_apelacion AS ENUM ('pendiente', 'ganada', 'cerrada')
    """)

    # ── Tabla: modulos ─────────────────────────────────────────────────────────
    op.create_table(
        "modulos",
        sa.Column("id", sa.SmallInteger(), primary_key=True, autoincrement=True),
        sa.Column("numero", sa.SmallInteger(), nullable=False),
        sa.Column("titulo", sa.String(80), nullable=False),
        sa.Column("etapa_startup", sa.String(80), nullable=False),
        sa.Column("color_token", sa.String(40), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("numero", name="uq_modulos_numero"),
    )

    # ── Tabla: sprints ─────────────────────────────────────────────────────────
    op.create_table(
        "sprints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("modulo_id", sa.SmallInteger(), sa.ForeignKey("modulos.id"), nullable=False),
        sa.Column("orden", sa.SmallInteger(), nullable=False),
        sa.Column("es_examen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("titulo", sa.String(120), nullable=False),
        sa.Column("objetivo", sa.Text(), nullable=False),
        sa.Column("ini_presupuesto", sa.SmallInteger(), nullable=False),
        sa.Column("ini_reputacion", sa.SmallInteger(), nullable=False),
        sa.Column("ini_velocidad", sa.SmallInteger(), nullable=False),
        sa.Column("ini_riesgo", sa.SmallInteger(), nullable=False),
        sa.Column("monedas_max", sa.SmallInteger(), nullable=False, server_default=sa.text("60")),
        sa.Column("escenario_jefe", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.UniqueConstraint("modulo_id", "orden", name="uq_sprints_modulo_orden"),
        sa.CheckConstraint("ini_presupuesto BETWEEN 0 AND 100", name="ck_sprints_ini_presupuesto"),
        sa.CheckConstraint("ini_reputacion BETWEEN 0 AND 100", name="ck_sprints_ini_reputacion"),
        sa.CheckConstraint("ini_velocidad BETWEEN 0 AND 100", name="ck_sprints_ini_velocidad"),
        sa.CheckConstraint("ini_riesgo BETWEEN 0 AND 100", name="ck_sprints_ini_riesgo"),
        sa.CheckConstraint(
            "escenario_jefe IS NULL OR es_examen = true",
            name="ck_sprints_escenario_solo_examen",
        ),
    )

    # ── Tabla: tarjetas ────────────────────────────────────────────────────────
    op.create_table(
        "tarjetas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("sprint_id", sa.Integer(), sa.ForeignKey("sprints.id"), nullable=False),
        sa.Column("tipo", postgresql.ENUM("normal", "evidencia", "justificacion", name="tipo_tarjeta", create_type=False), nullable=False),
        sa.Column("categoria", sa.String(60), nullable=False),
        sa.Column("personaje_nombre", sa.String(60), nullable=False),
        sa.Column("personaje_rol", sa.String(60), nullable=False),
        sa.Column("iniciales", sa.String(3), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("explicacion", sa.Text(), nullable=False),
        sa.Column("nota_abogado", sa.Text(), nullable=True),
        sa.Column("array_palabras_trampa", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("contenido_interactivo", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_tarjetas_sprint_activa_tipo", "tarjetas", ["sprint_id", "activa", "tipo"]
    )

    # ── Tabla: usuarios ────────────────────────────────────────────────────────
    op.create_table(
        "usuarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("correo", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("hash_contrasena", sa.String(72), nullable=False),
        sa.Column("perfil", postgresql.ENUM("estudiante", "desarrollador", "legal", name="perfil_usuario", create_type=False), nullable=False, server_default=sa.text("'desarrollador'")),
        sa.Column("rol", postgresql.ENUM("jugador", "admin", name="rol_usuario", create_type=False), nullable=False, server_default=sa.text("'jugador'")),
        sa.Column("estado_cuenta", postgresql.ENUM("activo", "suspendido", "pendiente_borrado", name="estado_cuenta", create_type=False), nullable=False, server_default=sa.text("'activo'")),
        sa.Column("zona_horaria", sa.String(60), nullable=False, server_default=sa.text("'America/Mexico_City'")),
        sa.Column("vidas", sa.SmallInteger(), nullable=False, server_default=sa.text("5")),
        sa.Column("vidas_base_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("monedas", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("xp", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("nivel", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("racha_actual", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("racha_maxima", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ultimo_dia_racha", sa.Date(), nullable=True),
        sa.Column("amparo_activo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        # Sin server_default: el INSERT siempre provee la estructura completa (03 §4 p.5)
        sa.Column("preferencias", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("inventario", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reto_diario", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ultimo_acceso", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eliminado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("vidas BETWEEN 0 AND 5", name="ck_usuarios_vidas"),
        sa.CheckConstraint("monedas >= 0", name="ck_usuarios_monedas"),
        sa.CheckConstraint("xp >= 0", name="ck_usuarios_xp"),
        sa.CheckConstraint("nivel >= 1", name="ck_usuarios_nivel"),
        sa.CheckConstraint("racha_actual >= 0", name="ck_usuarios_racha_actual"),
    )

    # ── Tabla: consentimientos ─────────────────────────────────────────────────
    op.create_table(
        "consentimientos",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("documento", sa.String(30), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("aceptado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ip", postgresql.INET(), nullable=True),
    )

    # ── Tabla: sesiones_refresh ────────────────────────────────────────────────
    op.create_table(
        "sesiones_refresh",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("dispositivo", sa.String(80), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revocado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reemplazado_por", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_sesiones_refresh_usuario_id", "sesiones_refresh", ["usuario_id"])

    # ── Tabla: restablecimientos_contrasena ────────────────────────────────────
    op.create_table(
        "restablecimientos_contrasena",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado_en", sa.DateTime(timezone=True), nullable=True),
    )

    # ── Tabla: dispositivos_push ───────────────────────────────────────────────
    op.create_table(
        "dispositivos_push",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("plataforma", sa.String(10), nullable=False),
        sa.Column("token", sa.Text(), nullable=False, unique=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ── Tabla: progreso_sprints ────────────────────────────────────────────────
    op.create_table(
        "progreso_sprints",
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), primary_key=True),
        sa.Column("sprint_id", sa.Integer(), sa.ForeignKey("sprints.id"), primary_key=True),
        sa.Column("estado", postgresql.ENUM("bloqueado", "disponible", "completado", name="estado_progreso", create_type=False), nullable=False, server_default=sa.text("'bloqueado'")),
        sa.Column("estrellas", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("mejor_aciertos", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("perfecto", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("completado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("estrellas BETWEEN 0 AND 3", name="ck_progreso_estrellas"),
    )

    # ── Tabla: intentos ────────────────────────────────────────────────────────
    op.create_table(
        "intentos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),  # sin default; lo pone el cliente
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("sprint_id", sa.Integer(), sa.ForeignKey("sprints.id"), nullable=False),
        sa.Column("tipo", postgresql.ENUM("sprint", "examen", name="tipo_intento", create_type=False), nullable=False),
        sa.Column("estado", postgresql.ENUM("en_curso", "completado", "quebrado", "aprobado", "reprobado", "abandonado", name="estado_intento", create_type=False), nullable=False, server_default=sa.text("'en_curso'")),
        sa.Column("ind_presupuesto", sa.SmallInteger(), nullable=False),
        sa.Column("ind_reputacion", sa.SmallInteger(), nullable=False),
        sa.Column("ind_velocidad", sa.SmallInteger(), nullable=False),
        sa.Column("ind_riesgo", sa.SmallInteger(), nullable=False),
        sa.Column("hp_jefe", sa.SmallInteger(), nullable=True),
        sa.Column("aciertos", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("parciales", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("errores", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("xp_ganada", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("monedas_ganadas", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tarjetas_asignadas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("marcado_revision", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pausado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pausa_acumulada_s", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("iniciado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("terminado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("ind_presupuesto BETWEEN 0 AND 100", name="ck_intentos_ind_presupuesto"),
        sa.CheckConstraint("ind_reputacion BETWEEN 0 AND 100", name="ck_intentos_ind_reputacion"),
        sa.CheckConstraint("ind_velocidad BETWEEN 0 AND 100", name="ck_intentos_ind_velocidad"),
        sa.CheckConstraint("ind_riesgo BETWEEN 0 AND 100", name="ck_intentos_ind_riesgo"),
        sa.CheckConstraint("hp_jefe IS NULL OR hp_jefe BETWEEN 0 AND 100", name="ck_intentos_hp_jefe"),
        sa.CheckConstraint("pausa_acumulada_s >= 0", name="ck_intentos_pausa_acumulada_s"),
    )
    op.create_index("ix_intentos_usuario_id", "intentos", ["usuario_id"])
    # Índice único parcial: solo un intento en_curso por usuario
    op.execute(
        "CREATE UNIQUE INDEX ix_intentos_en_curso ON intentos (usuario_id) WHERE estado = 'en_curso'"
    )

    # ── Tabla: respuestas ──────────────────────────────────────────────────────
    op.create_table(
        "respuestas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),  # sin default; lo pone el cliente
        sa.Column("intento_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("intentos.id"), nullable=False),
        sa.Column("tarjeta_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tarjetas.id"), nullable=False),
        sa.Column("veredicto", postgresql.ENUM("legal", "ilegal", "condicional", "escalar", name="veredicto", create_type=False), nullable=True),
        sa.Column("resultado", postgresql.ENUM("correcto", "parcial", "incorrecto", "tiempo_agotado", name="resultado_respuesta", create_type=False), nullable=False),
        sa.Column("segundos", sa.Numeric(5, 2), nullable=True),
        sa.Column("por_que_ok", sa.Boolean(), nullable=True),
        sa.Column("evidencia_ok", sa.Boolean(), nullable=True),
        sa.Column("justificacion_ok", sa.Boolean(), nullable=True),
        sa.Column("contraargumento_ok", sa.Boolean(), nullable=True),
        sa.Column("amparo_usado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("d_presupuesto", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("d_reputacion", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("d_velocidad", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("d_riesgo", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("xp", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("monedas", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("vidas_delta", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("respondido_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recibido_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("intento_id", "tarjeta_id", name="uq_respuestas_intento_tarjeta"),
    )
    op.create_index("ix_respuestas_intento_id", "respuestas", ["intento_id"])

    # ── Tabla: comodines ───────────────────────────────────────────────────────
    op.create_table(
        "comodines",
        sa.Column("id", sa.SmallInteger(), primary_key=True, autoincrement=True),
        sa.Column("clave", postgresql.ENUM("lupa", "abogado", "amparo", "congelar_racha", name="tipo_comodin", create_type=False), nullable=False, unique=True),
        sa.Column("nombre", sa.String(40), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("precio", sa.Integer(), nullable=False),
        sa.Column("permitido_en_examen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # ── Tabla: movimientos_economia ────────────────────────────────────────────
    op.create_table(
        "movimientos_economia",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("recurso", sa.String(10), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("saldo_resultante", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.String(30), nullable=False),
        sa.Column("detalle", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("referencia_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("recurso IN ('vidas', 'monedas', 'xp')", name="ck_movimientos_recurso"),
    )
    op.create_index("ix_movimientos_hist", "movimientos_economia", ["usuario_id", "creado_en"])

    # ── Tabla: apelaciones ─────────────────────────────────────────────────────
    op.create_table(
        "apelaciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("tarjeta_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tarjetas.id"), nullable=False),
        sa.Column("tarjeta_version", sa.Integer(), nullable=False),
        sa.Column("respuesta_origen_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("respuestas.id"), nullable=True),
        sa.Column("etapa", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("proxima_revision", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado", postgresql.ENUM("pendiente", "ganada", "cerrada", name="estado_apelacion", create_type=False), nullable=False, server_default=sa.text("'pendiente'")),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("etapa BETWEEN 1 AND 3", name="ck_apelaciones_etapa"),
    )
    op.create_index("ix_apelaciones_buzon", "apelaciones", ["usuario_id", "estado", "proxima_revision"])
    # Índice único parcial: solo una apelación pendiente por usuario+tarjeta
    op.execute(
        "CREATE UNIQUE INDEX ix_apelacion_abierta ON apelaciones (usuario_id, tarjeta_id) WHERE estado = 'pendiente'"
    )

    # ── Tabla: juicios_apelacion ───────────────────────────────────────────────
    op.create_table(
        "juicios_apelacion",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),  # sin default; lo pone el cliente
        sa.Column("apelacion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("apelaciones.id"), nullable=False),
        sa.Column("veredicto", postgresql.ENUM("legal", "ilegal", "condicional", "escalar", name="veredicto", create_type=False), nullable=True),
        sa.Column("resultado", postgresql.ENUM("correcto", "parcial", "incorrecto", "tiempo_agotado", name="resultado_respuesta", create_type=False), nullable=False),
        sa.Column("vida_recuperada", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("resuelto_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ── Tabla: notificaciones ──────────────────────────────────────────────────
    op.create_table(
        "notificaciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("titulo", sa.String(80), nullable=False),
        sa.Column("cuerpo", sa.String(200), nullable=False),
        sa.Column("referencia_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("programada_para", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enviada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estado", sa.String(12), nullable=False, server_default=sa.text("'pendiente'")),
    )
    op.create_index("ix_notificaciones_estado_programada", "notificaciones", ["estado", "programada_para"])

    # ── Tabla: insignias ───────────────────────────────────────────────────────
    op.create_table(
        "insignias",
        sa.Column("id", sa.SmallInteger(), primary_key=True, autoincrement=True),
        sa.Column("clave", sa.String(40), nullable=False, unique=True),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("icono", sa.String(40), nullable=False),
    )

    # ── Tabla: usuario_insignias ───────────────────────────────────────────────
    op.create_table(
        "usuario_insignias",
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), primary_key=True),
        sa.Column("insignia_id", sa.SmallInteger(), sa.ForeignKey("insignias.id"), primary_key=True),
        sa.Column("obtenida_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ── Tabla: certificados ────────────────────────────────────────────────────
    op.create_table(
        "certificados",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("modulo_id", sa.SmallInteger(), sa.ForeignKey("modulos.id"), nullable=False),
        sa.Column("intento_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("intentos.id"), nullable=False),
        sa.Column("folio", sa.String(20), nullable=False, unique=True),
        sa.Column("emitido_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("usuario_id", "modulo_id", name="uq_certificados_usuario_modulo"),
    )

    # ── Tabla: auditoria_admin ─────────────────────────────────────────────────
    op.create_table(
        "auditoria_admin",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("entidad", sa.String(40), nullable=False),
        sa.Column("entidad_id", sa.String(40), nullable=False),
        sa.Column("accion", sa.String(20), nullable=False),
        sa.Column("cambios", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    # Eliminar en orden inverso de dependencias
    op.drop_table("auditoria_admin")
    op.drop_table("certificados")
    op.drop_table("usuario_insignias")
    op.drop_table("insignias")
    op.drop_table("notificaciones")
    op.drop_table("juicios_apelacion")
    op.drop_index("ix_apelacion_abierta", table_name="apelaciones")
    op.drop_index("ix_apelaciones_buzon", table_name="apelaciones")
    op.drop_table("apelaciones")
    op.drop_index("ix_movimientos_hist", table_name="movimientos_economia")
    op.drop_table("movimientos_economia")
    op.drop_table("comodines")
    op.drop_index("ix_respuestas_intento_id", table_name="respuestas")
    op.drop_table("respuestas")
    op.execute("DROP INDEX IF EXISTS ix_intentos_en_curso")
    op.drop_index("ix_intentos_usuario_id", table_name="intentos")
    op.drop_table("intentos")
    op.drop_table("progreso_sprints")
    op.drop_table("dispositivos_push")
    op.drop_table("restablecimientos_contrasena")
    op.drop_index("ix_sesiones_refresh_usuario_id", table_name="sesiones_refresh")
    op.drop_table("sesiones_refresh")
    op.drop_table("consentimientos")
    op.drop_table("usuarios")
    op.drop_index("ix_tarjetas_sprint_activa_tipo", table_name="tarjetas")
    op.drop_table("tarjetas")
    op.drop_table("sprints")
    op.drop_table("modulos")

    # Eliminar tipos ENUM
    for tipo in [
        "estado_apelacion", "tipo_comodin", "estado_progreso", "estado_intento",
        "tipo_intento", "tipo_tarjeta", "resultado_respuesta", "veredicto",
        "estado_cuenta", "rol_usuario", "perfil_usuario",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {tipo}")

    op.execute("DROP EXTENSION IF EXISTS citext")
