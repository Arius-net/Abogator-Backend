from __future__ import annotations

import uuid
import pytest
from pydantic import ValidationError

from app.esquemas.contenido import (
    ContenidoInteractivo,
    DecisionFundamento,
    DecisionJefe,
    EscenarioJefe,
    EvidenciaContenido,
    MicroPregunta,
    OpcionMicroPregunta,
    VeredictoInfo,
    VeredictosDict,
)


def _crear_veredictos_validos() -> dict:
    return {
        "legal": {"resultado": "incorrecto", "d_presupuesto": 0, "d_reputacion": -5, "d_velocidad": 10, "d_riesgo": 25},
        "ilegal": {"resultado": "correcto", "d_presupuesto": -5, "d_reputacion": 5, "d_velocidad": -10, "d_riesgo": -20},
        "condicional": {"resultado": "parcial", "d_presupuesto": 0, "d_reputacion": 0, "d_velocidad": 0, "d_riesgo": 5},
        "escalar": {"resultado": "incorrecto", "d_presupuesto": -10, "d_reputacion": 0, "d_velocidad": -5, "d_riesgo": 0},
    }


def _crear_micro_pregunta_valida(tipo: str = "por_que") -> dict:
    return {
        "tipo": tipo,
        "enunciado": "¿Cuál es el motivo?",
        "opciones": [
            {"id": 1, "texto": "Opción 1", "es_correcta": True},
            {"id": 2, "texto": "Opción 2", "es_correcta": False},
        ],
    }


class TestContenidoInteractivoValidaciones:
    def test_contenido_normal_valido(self) -> None:
        raw = {
            "veredictos": _crear_veredictos_validos(),
            "evidencia": None,
            "micro_pregunta": _crear_micro_pregunta_valida("por_que"),
        }
        ci = ContenidoInteractivo.model_validate(raw)
        ci.validar_para_tipo_tarjeta("normal")
        assert ci.veredictos.ilegal.resultado == "correcto"

    def test_rechaza_dos_veredictos_correctos(self) -> None:
        v = _crear_veredictos_validos()
        v["legal"]["resultado"] = "correcto"
        with pytest.raises(ValidationError):
            ContenidoInteractivo.model_validate({
                "veredictos": v,
                "evidencia": None,
                "micro_pregunta": _crear_micro_pregunta_valida(),
            })

    def test_rechaza_cero_veredictos_correctos(self) -> None:
        v = _crear_veredictos_validos()
        v["ilegal"]["resultado"] = "incorrecto"
        with pytest.raises(ValidationError):
            ContenidoInteractivo.model_validate({
                "veredictos": v,
                "evidencia": None,
                "micro_pregunta": _crear_micro_pregunta_valida(),
            })

    def test_rechaza_mas_de_dos_parciales(self) -> None:
        v = _crear_veredictos_validos()
        v["legal"]["resultado"] = "parcial"
        v["escalar"]["resultado"] = "parcial"
        with pytest.raises(ValidationError):
            ContenidoInteractivo.model_validate({
                "veredictos": v,
                "evidencia": None,
                "micro_pregunta": _crear_micro_pregunta_valida(),
            })

    def test_rechaza_deltas_fuera_de_rango(self) -> None:
        v = _crear_veredictos_validos()
        v["legal"]["d_presupuesto"] = 150
        with pytest.raises(ValidationError):
            ContenidoInteractivo.model_validate({
                "veredictos": v,
                "evidencia": None,
                "micro_pregunta": _crear_micro_pregunta_valida(),
            })

    def test_tarjeta_normal_rechaza_evidencia(self) -> None:
        raw = {
            "veredictos": _crear_veredictos_validos(),
            "evidencia": {
                "requerida": True,
                "formato": "codigo",
                "nombre_archivo": "test.py",
                "contenido_texto": "linea 1\nlinea 2",
                "lineas_infractoras": [1],
            },
            "micro_pregunta": _crear_micro_pregunta_valida("por_que"),
        }
        ci = ContenidoInteractivo.model_validate(raw)
        with pytest.raises(ValueError):
            ci.validar_para_tipo_tarjeta("normal")

    def test_tarjeta_evidencia_valida(self) -> None:
        raw = {
            "veredictos": _crear_veredictos_validos(),
            "evidencia": {
                "requerida": True,
                "formato": "codigo",
                "nombre_archivo": "app.dart",
                "contenido_texto": "void main() {\n  print('hola');\n}",
                "lineas_infractoras": [2],
            },
            "micro_pregunta": _crear_micro_pregunta_valida("por_que"),
        }
        ci = ContenidoInteractivo.model_validate(raw)
        ci.validar_para_tipo_tarjeta("evidencia")
        assert ci.evidencia is not None

    def test_tarjeta_evidencia_rechaza_linea_inexistente(self) -> None:
        with pytest.raises(ValidationError):
            EvidenciaContenido(
                requerida=True,
                formato="codigo",
                nombre_archivo="main.py",
                contenido_texto="linea 1\nlinea 2",
                lineas_infractoras=[10],
            )

    def test_micro_pregunta_rechaza_ambas_correctas(self) -> None:
        with pytest.raises(ValidationError):
            MicroPregunta(
                tipo="por_que",
                enunciado="¿Por qué?",
                opciones=[
                    OpcionMicroPregunta(id=1, texto="A", es_correcta=True),
                    OpcionMicroPregunta(id=2, texto="B", es_correcta=True),
                ],
            )

    def test_micro_pregunta_rechaza_ids_duplicados(self) -> None:
        with pytest.raises(ValidationError):
            MicroPregunta(
                tipo="por_que",
                enunciado="¿Por qué?",
                opciones=[
                    OpcionMicroPregunta(id=1, texto="A", es_correcta=True),
                    OpcionMicroPregunta(id=1, texto="B", es_correcta=False),
                ],
            )


class TestEscenarioJefeValidaciones:
    def _crear_escenario_valido(self) -> dict:
        decisiones = []
        for i in range(1, 11):
            hora = 0 if i <= 3 else (6 if i <= 6 else (24 if i <= 8 else 72))
            decisiones.append({
                "orden": i,
                "tarjeta_id": str(uuid.uuid4()),
                "hora_crisis": hora,
                "replica_jefe": f"Replica {i}",
                "fundamentos": [
                    {"id": 1, "texto": "Fundamento A", "es_correcta": True},
                    {"id": 2, "texto": "Fundamento B", "es_correcta": False},
                ],
            })
        return {
            "nombre_jefe": "Inspectora Vega",
            "titulo_crisis": "Brecha de Datos",
            "descripcion": "Han robado la base de datos...",
            "hp_inicial": 100,
            "dano_por_golpe": 20,
            "segundos_decision": 15,
            "segundos_contraargumento": 8,
            "decisiones": decisiones,
        }

    def test_escenario_valido_pasa(self) -> None:
        data = self._crear_escenario_valido()
        esc = EscenarioJefe.model_validate(data)
        assert len(esc.decisiones) == 10
        assert esc.hp_inicial == 100

    def test_escenario_rechaza_menos_de_10_decisiones(self) -> None:
        data = self._crear_escenario_valido()
        data["decisiones"] = data["decisiones"][:9]
        with pytest.raises(ValidationError):
            EscenarioJefe.model_validate(data)

    def test_escenario_rechaza_hora_crisis_decreciente(self) -> None:
        data = self._crear_escenario_valido()
        data["decisiones"][1]["hora_crisis"] = 24
        data["decisiones"][2]["hora_crisis"] = 6
        with pytest.raises(ValidationError):
            EscenarioJefe.model_validate(data)

    def test_escenario_rechaza_hora_crisis_invalida(self) -> None:
        data = self._crear_escenario_valido()
        data["decisiones"][0]["hora_crisis"] = 12
        with pytest.raises(ValidationError):
            EscenarioJefe.model_validate(data)

    def test_escenario_rechaza_hp_negativo(self) -> None:
        data = self._crear_escenario_valido()
        data["hp_inicial"] = -50
        with pytest.raises(ValidationError):
            EscenarioJefe.model_validate(data)
