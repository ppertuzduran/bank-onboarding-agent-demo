from __future__ import annotations

import logging
import re
from functools import lru_cache
from re import Pattern
from typing import Final

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings, get_settings


class PIIRedactor(logging.Filter):
    """Redacta identificadores largos (posibles document_id) de los logs."""

    _PATTERNS: Final[list[tuple[Pattern[str], str]]] = [
        (re.compile(r"\b\d{5,20}\b"), "[REDACTED_ID]"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern, replacement in self._PATTERNS:
            message = pattern.sub(replacement, message)
        record.msg = message
        record.args = ()
        return True


class LoggingConfigurator:
    """Compat: delega en `app.audit.LoggingBootstrap` (JSON estructurado + redact)."""

    @classmethod
    def configure(cls) -> None:
        from app.audit import LoggingBootstrap

        LoggingBootstrap.configure()


class EncryptionService:
    """Encapsula Fernet para cifrar/descifrar documentos at-rest.

    Fernet = AES-128-CBC + HMAC-SHA256 (clave única urlsafe-base64 de 32 bytes).
    En Fase AWS, esta clase se reemplaza por un wrapper sobre KMS + S3 SSE.
    """

    def __init__(self, key: str) -> None:
        if not key:
            raise RuntimeError(
                "FERNET_KEY no está configurada. Generar con: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        self._fernet: Fernet = Fernet(key.encode())

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> EncryptionService:
        settings = settings or get_settings()
        return cls(settings.fernet_key)

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        try:
            return self._fernet.decrypt(token)
        except InvalidToken as exc:
            raise RuntimeError("No se pudo descifrar: clave inválida o datos corruptos") from exc

    def encrypt_text(self, text: str) -> bytes:
        return self.encrypt(text.encode("utf-8"))

    def decrypt_text(self, token: bytes) -> str:
        return self.decrypt(token).decode("utf-8")


@lru_cache(maxsize=1)
def get_encryption_service() -> EncryptionService:
    return EncryptionService.from_settings()
