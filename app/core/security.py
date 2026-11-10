from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import timedelta
from typing import Any

import bcrypt
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_config
from app.core.reloj import now



BCRYPT_ROUNDS = 12


def hashear_contrasena(contrasena: str) -> str:
    """Devuelve el hash bcrypt de la contraseña."""
    return bcrypt.hashpw(contrasena.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    """Compara la contraseña con el hash almacenado."""
    return bcrypt.checkpw(contrasena.encode(), hash_guardado.encode())



def crear_access_token(
    sub: str,
    rol: str,
    perfil: str,
    minutos: int | None = None,
) -> str:
    """Crea un JWT HS256 con claims sub, rol, perfil y exp."""
    cfg = get_config()
    duracion = timedelta(minutes=minutos or cfg.ACCESS_TOKEN_MIN)
    exp = now() + duracion
    payload = {"sub": sub, "rol": rol, "perfil": perfil, "exp": exp}
    return jwt.encode(payload, cfg.JWT_SECRET, algorithm="HS256")


def decodificar_access_token(token: str) -> dict[str, Any]:
    """Decodifica y valida un JWT. Lanza jwt.ExpiredSignatureError / jwt.InvalidTokenError."""
    cfg = get_config()
    return jwt.decode(token, cfg.JWT_SECRET, algorithms=["HS256"])



def generar_refresh_token() -> str:
    """Genera 32 bytes aleatorios en hex (64 caracteres). Se devuelve al cliente."""
    return secrets.token_hex(32)


def hashear_token(token: str) -> str:
    """SHA-256 del token. Es lo que se guarda en la base de datos."""
    return hashlib.sha256(token.encode()).hexdigest()



def _clave_intento(intento_id: str) -> bytes:
    """
    Deriva la clave de cifrado del paquete de un intento.
    clave_intento = HMAC-SHA256(PAQUETE_SECRET, intento_id)
    No se guarda; se puede recalcular siempre (07 §2).
    """
    cfg = get_config()
    return hmac.new(
        cfg.PAQUETE_SECRET.encode(),
        intento_id.encode(),
        hashlib.sha256,
    ).digest()


def cifrar_resolucion(
    intento_id: str,
    tarjeta_id: str,
    payload_json: bytes,
) -> bytes:
    """
    Cifra con AES-256-GCM.
    AAD = "{intento_id}:{tarjeta_id}"
    Devuelve nonce(12) || ciphertext || tag.
    """
    clave = _clave_intento(intento_id)
    nonce = os.urandom(12)
    aad = f"{intento_id}:{tarjeta_id}".encode()
    cifrado = AESGCM(clave).encrypt(nonce, payload_json, aad)
    return nonce + cifrado


def descifrar_resolucion(
    intento_id: str,
    tarjeta_id: str,
    blob: bytes,
) -> bytes:
    """Invierte cifrar_resolucion. Lanza InvalidTag si está corrupto."""
    clave = _clave_intento(intento_id)
    nonce, ciphertext = blob[:12], blob[12:]
    aad = f"{intento_id}:{tarjeta_id}".encode()
    return AESGCM(clave).decrypt(nonce, ciphertext, aad)


def clave_intento_b64(intento_id: str) -> str:
    """Devuelve la clave del intento en base64 (para incluirla en el paquete)."""
    import base64
    return base64.b64encode(_clave_intento(intento_id)).decode()
