import enum


class PerfilUsuario(str, enum.Enum):
    estudiante = "estudiante"
    desarrollador = "desarrollador"
    legal = "legal"


class RolUsuario(str, enum.Enum):
    jugador = "jugador"
    admin = "admin"


class EstadoCuenta(str, enum.Enum):
    activo = "activo"
    suspendido = "suspendido"
    pendiente_borrado = "pendiente_borrado"


class Veredicto(str, enum.Enum):
    legal = "legal"
    ilegal = "ilegal"
    condicional = "condicional"
    escalar = "escalar"


class ResultadoRespuesta(str, enum.Enum):
    correcto = "correcto"
    parcial = "parcial"
    incorrecto = "incorrecto"
    tiempo_agotado = "tiempo_agotado"


class TipoTarjeta(str, enum.Enum):
    normal = "normal"
    evidencia = "evidencia"
    justificacion = "justificacion"


class TipoIntento(str, enum.Enum):
    sprint = "sprint"
    examen = "examen"


class EstadoIntento(str, enum.Enum):
    en_curso = "en_curso"
    completado = "completado"
    quebrado = "quebrado"
    aprobado = "aprobado"
    reprobado = "reprobado"
    abandonado = "abandonado"


class EstadoProgreso(str, enum.Enum):
    bloqueado = "bloqueado"
    disponible = "disponible"
    completado = "completado"


class TipoComodin(str, enum.Enum):
    lupa = "lupa"
    abogado = "abogado"
    amparo = "amparo"
    congelar_racha = "congelar_racha"


class EstadoApelacion(str, enum.Enum):
    pendiente = "pendiente"
    ganada = "ganada"
    cerrada = "cerrada"


class ResultadoVeredicto(str, enum.Enum):
    correcto = "correcto"
    parcial = "parcial"
    incorrecto = "incorrecto"
