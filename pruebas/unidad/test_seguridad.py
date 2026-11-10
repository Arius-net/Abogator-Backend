import json
import pytest
from app.core import security

def test_hash_contrasena_y_verificacion() -> None:
    password = "SuperPasswordSegura123!"
    hash_gen = security.hashear_contrasena(password)
    assert hash_gen != password
    assert security.verificar_contrasena(password, hash_gen) is True
    assert security.verificar_contrasena("otra_password", hash_gen) is False

def test_jwt_creacion_y_decodificacion() -> None:
    token = security.crear_access_token(
        sub="00000000-0000-0000-0000-000000000001",
        rol="jugador",
        perfil="desarrollador",
        minutos=15,
    )
    datos = security.decodificar_access_token(token)
    assert datos["sub"] == "00000000-0000-0000-0000-000000000001"
    assert datos["rol"] == "jugador"
    assert datos["perfil"] == "desarrollador"
    assert "exp" in datos

def test_hash_refresh_token() -> None:
    raw_token = security.generar_refresh_token()
    assert len(raw_token) == 64
    hash1 = security.hashear_token(raw_token)
    hash2 = security.hashear_token(raw_token)
    assert hash1 == hash2
    assert len(hash1) == 64

def test_cifrado_y_descifrado_resolucion_paquete() -> None:
    intento_id = "11111111-2222-3333-4444-555555555555"
    tarjeta_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    
    contenido = {
        "veredictos": {"legal": {"resultado": "correcto"}},
        "explicacion": "Artículo 9 cumplido.",
        "lineas_infractoras": [1, 2],
        "opcion_correcta_micro_pregunta": 1,
    }
    raw_bytes = json.dumps(contenido).encode("utf-8")
    
    blob_cifrado = security.cifrar_resolucion(intento_id, tarjeta_id, raw_bytes)
    assert blob_cifrado != raw_bytes
    
    descifrado = security.descifrar_resolucion(intento_id, tarjeta_id, blob_cifrado)
    assert descifrado == raw_bytes
    assert json.loads(descifrado.decode("utf-8")) == contenido

def test_cifrado_resolucion_falla_con_aad_distinto() -> None:
    intento_id = "11111111-2222-3333-4444-555555555555"
    tarjeta_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    otro_intento = "99999999-9999-9999-9999-999999999999"
    
    blob_cifrado = security.cifrar_resolucion(intento_id, tarjeta_id, b"secreto")
    with pytest.raises(Exception):
        # AAD diferente o clave diferente -> falla verificación AES-GCM
        security.descifrar_resolucion(otro_intento, tarjeta_id, blob_cifrado)
