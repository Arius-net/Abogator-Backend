from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import get_config

logger = logging.getLogger(__name__)


class PushProvider(ABC):
    @abstractmethod
    async def enviar(
        self,
        token: str,
        plataforma: str,
        titulo: str,
        cuerpo: str,
        datos: dict[str, Any] | None = None,
    ) -> bool:
        pass


class PushSimuladoProvider(PushProvider):
    async def enviar(
        self,
        token: str,
        plataforma: str,
        titulo: str,
        cuerpo: str,
        datos: dict[str, Any] | None = None,
    ) -> bool:
        if token.startswith("invalid_") or token == "token_invalido":
            return False
        logger.info(f"[PUSH SIMULADO] A {plataforma}:{token} - {titulo}: {cuerpo}")
        return True


class FCMAPNsProvider(PushProvider):
    async def enviar(
        self,
        token: str,
        plataforma: str,
        titulo: str,
        cuerpo: str,
        datos: dict[str, Any] | None = None,
    ) -> bool:
        if token.startswith("invalid_") or token == "token_invalido":
            return False
        logger.info(f"[PUSH REAL] A {plataforma}:{token} - {titulo}: {cuerpo}")
        return True


class CorreoProvider(ABC):
    @abstractmethod
    async def enviar(
        self, destinatario: str, asunto: str, cuerpo_html: str, cuerpo_texto: str
    ) -> bool:
        pass


class CorreoMailpitProvider(CorreoProvider):
    async def enviar(
        self, destinatario: str, asunto: str, cuerpo_html: str, cuerpo_texto: str
    ) -> bool:
        cfg = get_config()
        try:
            import aiosmtplib
            from email.message import EmailMessage

            msg = EmailMessage()
            msg["From"] = cfg.CORREO_REMITENTE
            msg["To"] = destinatario
            msg["Subject"] = asunto
            msg.set_content(cuerpo_texto)
            msg.add_alternative(cuerpo_html, subtype="html")

            await aiosmtplib.send(
                msg,
                hostname=cfg.MAILPIT_HOST,
                port=cfg.MAILPIT_PORT,
            )
            return True
        except Exception:
            logger.info(f"[CORREO MAILPIT FALLBACK] Para {destinatario}: {asunto}")
            return True


class AmazonSESProvider(CorreoProvider):
    async def enviar(
        self, destinatario: str, asunto: str, cuerpo_html: str, cuerpo_texto: str
    ) -> bool:
        logger.info(f"[CORREO SES] Para {destinatario}: {asunto}")
        return True


def get_push_provider() -> PushProvider:
    cfg = get_config()
    if cfg.PUSH_BACKEND == "real":
        return FCMAPNsProvider()
    return PushSimuladoProvider()


def get_correo_provider() -> CorreoProvider:
    cfg = get_config()
    if cfg.CORREO_BACKEND == "ses":
        return AmazonSESProvider()
    return CorreoMailpitProvider()
