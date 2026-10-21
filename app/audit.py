"""Audit logging estructurado en JSON para eventos sensibles.

Un entorno bancario exige trazabilidad completa de decisiones de aptitud,
accesos a documentación cifrada y escalamientos. Este módulo centraliza
los eventos auditables en un formato JSON uniforme, redactando PII.

En AWS, el logger se puede dirigir a CloudWatch Logs → Firehose → S3 con
retención larga + Athena para consultas.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.config import get_settings

_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{5,20}\b"), "[REDACTED_ID]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
]


class AuditEvent(StrEnum):
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    RATE_LIMITED = "rate_limit.exceeded"
    ONBOARDING_STARTED = "onboarding.started"
    ONBOARDING_COMPLETED = "onboarding.completed"
    ONBOARDING_ESCALATED = "onboarding.escalated"
    DOCUMENT_DECRYPTED = "document.decrypted"
    POLICY_RETRIEVED = "policy.retrieved"


class _JsonFormatter(logging.Formatter):
    """Formatea cada registro como una línea JSON válida."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self._redact(record.getMessage()),
        }
        for key in ("event", "request_id", "session_id", "api_key_id", "decision", "status_code"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update({k: self._redact_value(v) for k, v in extra.items()})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _redact(self, text: str) -> str:
        for pattern, replacement in _PII_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    def _redact_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._redact(value)
        return value


class AuditLogger:
    """Fachada tipada sobre un `logging.Logger` para eventos de auditoría."""

    def __init__(self, name: str = "audit") -> None:
        self._logger: logging.Logger = logging.getLogger(name)

    def log(
        self,
        event: AuditEvent,
        *,
        request_id: str | None = None,
        session_id: str | None = None,
        api_key_id: str | None = None,
        decision: str | None = None,
        status_code: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._logger.info(
            event.value,
            extra={
                "event": event.value,
                "request_id": request_id,
                "session_id": session_id,
                "api_key_id": api_key_id,
                "decision": decision,
                "status_code": status_code,
                "extra_fields": extra or {},
            },
        )


class LoggingBootstrap:
    """Configura logging raíz una sola vez con formato JSON."""

    _configured: bool = False

    @classmethod
    def configure(cls) -> None:
        if cls._configured:
            return
        settings = get_settings()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        # Silenciar access logs ruidosos de uvicorn (ya tenemos request_id).
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        cls._configured = True
        logging.getLogger("app").info(
            "Logging configurado",
            extra={
                "extra_fields": {
                    "service": settings.service_name,
                    "version": settings.service_version,
                    "environment": settings.environment.value,
                }
            },
        )


def get_audit_logger() -> AuditLogger:
    return AuditLogger()
