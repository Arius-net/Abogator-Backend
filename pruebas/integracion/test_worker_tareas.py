from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.core.reloj import now
from app.modelos.apelaciones import Apelacion, Notificacion
from app.modelos.enums import EstadoApelacion, EstadoCuenta, EstadoIntento, PerfilUsuario, RolUsuario, TipoIntento
from app.modelos.juego import Intento
from app.modelos.usuarios import DispositivoPush, SesionRefresh, Usuario
from worker.tareas.anonimizacion import tarea_anonimizacion
from worker.tareas.apelaciones_vencidas import tarea_apelaciones_vencidas
from worker.tareas.cierre_racha import tarea_cierre_racha
from worker.tareas.envio_push import tarea_envio_push
from worker.tareas.intentos_abandonados import tarea_intentos_abandonados
from worker.tareas.pausas_examen_vencidas import tarea_pausas_examen_vencidas
from worker.tareas.recordatorio_racha import tarea_recordatorio_racha
from worker.tareas.vidas_llenas import tarea_vidas_llenas
from worker.ventana import calcular_programada_para


def _crear_usuario_test(
    uid: uuid.UUID | None = None,
    racha_actual: int = 1,
    ultimo_dia_racha=None,
    vidas: int = 5,
    congelar_racha: int = 0,
    preferencias: dict | None = None,
    estado_cuenta=EstadoCuenta.activo,
    eliminado_en=None,
) -> Usuario:
    if uid is None:
        uid = uuid.uuid4()
    if preferencias is None:
        preferencias = {"notif_apelaciones": True, "notif_vidas": True, "notif_racha": True}
    return Usuario(
        id=uid,
        nombre="Dev User",
        correo=f"dev_{uid.hex[:6]}@abogator.io",
        hash_contrasena="hash",
        perfil=PerfilUsuario.desarrollador,
        rol=RolUsuario.jugador,
        monedas=100,
        xp=50,
        nivel=1,
        vidas=vidas,
        vidas_base_en=now(),
        amparo_activo=False,
        racha_actual=racha_actual,
        racha_maxima=racha_actual,
        ultimo_dia_racha=ultimo_dia_racha or now().date(),
        zona_horaria="America/Mexico_City",
        preferencias=preferencias,
        inventario={"lupa": 0, "abogado": 0, "amparo": 0, "congelar_racha": congelar_racha},
        reto_diario={},
        estado_cuenta=estado_cuenta,
        eliminado_en=eliminado_en,
    )


def test_calcular_programada_para_ventana_envio():
    tz = ZoneInfo("America/Mexico_City")

    dentro_ventana = datetime(2026, 11, 21, 14, 30, 0, tzinfo=tz).astimezone(timezone.utc)
    res_dentro = calcular_programada_para(dentro_ventana, "America/Mexico_City")
    assert res_dentro == dentro_ventana

    despues_21 = datetime(2026, 11, 21, 22, 15, 0, tzinfo=tz).astimezone(timezone.utc)
    res_despues = calcular_programada_para(despues_21, "America/Mexico_City")
    res_despues_local = res_despues.astimezone(tz)
    assert res_despues_local.hour == 9
    assert res_despues_local.minute == 0
    assert res_despues_local.day == 22

    antes_9 = datetime(2026, 11, 21, 6, 45, 0, tzinfo=tz).astimezone(timezone.utc)
    res_antes = calcular_programada_para(antes_9, "America/Mexico_City")
    res_antes_local = res_antes.astimezone(tz)
    assert res_antes_local.hour == 9
    assert res_antes_local.minute == 0
    assert res_antes_local.day == 21


@pytest.mark.asyncio
async def test_tarea_apelaciones_vencidas_singular_y_plural():
    uid1 = uuid.uuid4()
    uid2 = uuid.uuid4()
    u1 = _crear_usuario_test(uid=uid1)
    u2 = _crear_usuario_test(uid=uid2)

    sesion = AsyncMock()

    res_subq = MagicMock()
    res_subq.all.return_value = [(uid1, 1), (uid2, 3)]

    res_existente = MagicMock()
    res_existente.first.return_value = None

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        if "GROUP BY" in stmt_str or "group_by" in stmt_str.lower() or "count" in stmt_str.lower():
            return res_subq
        return res_existente

    sesion.execute = AsyncMock(side_effect=mock_execute)

    async def mock_get(cls, key):
        if key == uid1:
            return u1
        if key == uid2:
            return u2
        return None

    sesion.get = AsyncMock(side_effect=mock_get)
    notifs_agregadas = []
    sesion.add = lambda n: notifs_agregadas.append(n)

    creadas = await tarea_apelaciones_vencidas(sesion)
    assert creadas == 2
    assert len(notifs_agregadas) == 2
    assert notifs_agregadas[0].cuerpo == "Tienes 1 juicio de apelación pendiente"
    assert notifs_agregadas[1].cuerpo == "Tienes 3 juicios de apelación pendientes"


@pytest.mark.asyncio
async def test_tarea_envio_push_y_desactiva_token_invalido():
    uid = uuid.uuid4()
    notif = Notificacion(
        id=uuid.uuid4(),
        usuario_id=uid,
        tipo="apelacion",
        titulo="Alerta",
        cuerpo="Prueba",
        programada_para=now() - timedelta(minutes=5),
        estado="pendiente",
    )
    dev_valido = DispositivoPush(id=uuid.uuid4(), usuario_id=uid, plataforma="android", token="token_bueno", activo=True)
    dev_invalido = DispositivoPush(id=uuid.uuid4(), usuario_id=uid, plataforma="ios", token="invalid_token", activo=True)

    sesion = AsyncMock()
    res_notifs = MagicMock()
    res_notifs.scalars.return_value = [notif]

    res_devs = MagicMock()
    res_devs.scalars.return_value = [dev_valido, dev_invalido]

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        if "notificaciones" in stmt_str:
            return res_notifs
        return res_devs

    sesion.execute = AsyncMock(side_effect=mock_execute)

    enviadas = await tarea_envio_push(sesion)
    assert enviadas == 1
    assert notif.estado == "enviada"
    assert dev_invalido.activo is False
    assert dev_valido.activo is True


@pytest.mark.asyncio
async def test_tarea_vidas_llenas_notifica_al_llegar_a_cinco():
    uid = uuid.uuid4()
    u = _crear_usuario_test(uid=uid, vidas=0)
    u.vidas_base_en = now() - timedelta(hours=10)

    sesion = AsyncMock()
    res_users = MagicMock()
    res_users.scalars.return_value = [u]

    res_ex = MagicMock()
    res_ex.first.return_value = None

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        if "usuarios" in stmt_str:
            return res_users
        return res_ex

    sesion.execute = AsyncMock(side_effect=mock_execute)
    notifs = []
    sesion.add = lambda n: notifs.append(n)

    creadas = await tarea_vidas_llenas(sesion)
    assert creadas == 1
    assert len(notifs) == 1
    assert "5/5" in notifs[0].cuerpo


@pytest.mark.asyncio
async def test_tarea_cierre_racha_consume_congelar_o_reinicia():
    tz = ZoneInfo("America/Mexico_City")
    hoy_local = now().astimezone(tz).date()
    hace_dos_dias = hoy_local - timedelta(days=2)
    u_congelar = _crear_usuario_test(racha_actual=5, ultimo_dia_racha=hace_dos_dias, congelar_racha=1)
    u_sin_congelar = _crear_usuario_test(racha_actual=3, ultimo_dia_racha=hace_dos_dias, congelar_racha=0)

    sesion = AsyncMock()
    res = MagicMock()
    res.scalars.return_value = [u_congelar, u_sin_congelar]
    sesion.execute = AsyncMock(return_value=res)

    afectados = await tarea_cierre_racha(sesion)
    assert afectados == 2
    assert u_congelar.inventario["congelar_racha"] == 0
    assert u_congelar.racha_actual == 5
    assert u_sin_congelar.racha_actual == 0


@pytest.mark.asyncio
async def test_tarea_recordatorio_racha_a_las_19_horas():
    tz = ZoneInfo("America/Mexico_City")
    ahora_19 = datetime.now(tz).replace(hour=19, minute=5, second=0)

    with patch("worker.tareas.recordatorio_racha.now", return_value=ahora_19):
        u = _crear_usuario_test(racha_actual=4, ultimo_dia_racha=ahora_19.date() - timedelta(days=1))

        sesion = AsyncMock()
        res_users = MagicMock()
        res_users.scalars.return_value = [u]

        res_ex = MagicMock()
        res_ex.first.return_value = None

        async def mock_execute(stmt):
            stmt_str = str(stmt)
            if "usuarios" in stmt_str:
                return res_users
            return res_ex

        sesion.execute = AsyncMock(side_effect=mock_execute)
        notifs = []
        sesion.add = lambda n: notifs.append(n)

        creadas = await tarea_recordatorio_racha(sesion)
        assert creadas == 1
        assert len(notifs) == 1
        assert "4 días" in notifs[0].cuerpo


@pytest.mark.asyncio
async def test_tarea_intentos_abandonados_24h():
    it = Intento(
        id=uuid.uuid4(),
        usuario_id=uuid.uuid4(),
        sprint_id=1,
        tipo=TipoIntento.sprint,
        estado=EstadoIntento.en_curso,
        iniciado_en=now() - timedelta(hours=25),
    )

    sesion = AsyncMock()
    res = MagicMock()
    res.scalars.return_value = [it]
    sesion.execute = AsyncMock(return_value=res)

    cerrados = await tarea_intentos_abandonados(sesion)
    assert cerrados == 1
    assert it.estado == EstadoIntento.abandonado


@pytest.mark.asyncio
async def test_tarea_pausas_examen_vencidas():
    it = Intento(
        id=uuid.uuid4(),
        usuario_id=uuid.uuid4(),
        sprint_id=6,
        tipo=TipoIntento.examen,
        estado=EstadoIntento.en_curso,
        pausado_en=now() - timedelta(seconds=700),
        pausa_acumulada_s=0,
    )

    sesion = AsyncMock()
    res = MagicMock()
    res.scalars.return_value = [it]
    sesion.execute = AsyncMock(return_value=res)

    cerrados = await tarea_pausas_examen_vencidas(sesion)
    assert cerrados == 1
    assert it.estado == EstadoIntento.abandonado


@pytest.mark.asyncio
async def test_tarea_anonimizacion_a_los_30_dias():
    u = _crear_usuario_test(
        estado_cuenta=EstadoCuenta.pendiente_borrado,
        eliminado_en=now() - timedelta(days=35),
    )

    sesion = AsyncMock()
    res = MagicMock()
    res.scalars.return_value = [u]
    sesion.execute = AsyncMock(return_value=res)

    anonimizados = await tarea_anonimizacion(sesion)
    assert anonimizados == 1
    assert u.nombre == "Usuario Eliminado"
    assert u.hash_contrasena == "*"
    assert u.correo.startswith("eliminado+")
