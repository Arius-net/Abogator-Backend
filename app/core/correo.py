from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class CorreoProvider(ABC):
    """Interfaz de envío de correos."""

    @abstractmethod
    async def enviar_recuperacion(
        self,
        destinatario: str,
        nombre: str,
        enlace: str,
    ) -> None:
        """Envía el correo de recuperación de contraseña."""
        ...


class CorreoSimulado(CorreoProvider):
    """Registra en log en lugar de enviar. Útil en pruebas y local."""

    async def enviar_recuperacion(
        self,
        destinatario: str,
        nombre: str,
        enlace: str,
    ) -> None:
        prefijo = destinatario[:3] + "***"
        logger.info(
            "CORREO SIMULADO | recuperacion | destinatario=%s | enlace=%s",
            prefijo,
            enlace,
        )


class CorreoMailpit(CorreoProvider):
    """Envía a Mailpit via SMTP (local). No para producción."""

    async def enviar_recuperacion(
        self,
        destinatario: str,
        nombre: str,
        enlace: str,
    ) -> None:
        import aiosmtplib
        from email.mime.text import MIMEText

        from app.core.config import get_config

        cfg = get_config()
        cuerpo = (
            f"Hola {nombre},\n\n"
            f"Haz clic en el siguiente enlace para restablecer tu contraseña "
            f"(válido 30 minutos):\n\n{enlace}\n\n"
            "Si no solicitaste esto, ignora este correo.\n\n"
            "— AboGator"
        )
        msg = MIMEText(cuerpo, "plain", "utf-8")
        msg["Subject"] = "Restablece tu contraseña · AboGator"
        msg["From"] = cfg.CORREO_REMITENTE
        msg["To"] = destinatario

        await aiosmtplib.send(
            msg,
            hostname=cfg.MAILPIT_HOST,
            port=cfg.MAILPIT_PORT,
            start_tls=False,
        )


class CorreoSES(CorreoProvider):
    async def enviar_recuperacion(
        self,
        destinatario: str,
        nombre: str,
        enlace: str,
    ) -> None:
        raise NotImplementedError("Proveedor SES aún no configurado. Ver 11_pendientes.md.")


def get_correo_provider() -> CorreoProvider:
    from app.core.config import get_config

    backend = get_config().CORREO_BACKEND
    if backend == "ses":
        return CorreoSES()
    if backend == "mailpit":
        return CorreoMailpit()
    return CorreoSimulado()
