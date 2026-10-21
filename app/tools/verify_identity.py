"""Mock de verificación de identidad.

Determinista por `document_id`: la misma cédula siempre produce la misma salida.
Usa solo librerías estándar (`hashlib`, `random`).
"""

from __future__ import annotations

import hashlib
import random

from app.schemas import IdentityCheckResult


class IdentityVerifier:
    """Simula una llamada a un proveedor de verificación de identidad (p. ej., Veriff)."""

    def __init__(self, fail_rate: float = 0.1, low_confidence_rate: float = 0.2) -> None:
        if not 0.0 <= fail_rate <= 1.0:
            raise ValueError("fail_rate debe estar en [0, 1]")
        if not 0.0 <= low_confidence_rate <= 1.0:
            raise ValueError("low_confidence_rate debe estar en [0, 1]")
        self._fail_rate: float = fail_rate
        self._low_confidence_rate: float = low_confidence_rate

    def execute(self, document_id: str) -> IdentityCheckResult:
        rng = self._seeded_rng(document_id)
        roll = rng.random()
        if roll < self._fail_rate:
            return IdentityCheckResult(verified=False, confidence=round(rng.uniform(0.3, 0.6), 2))
        if roll < self._fail_rate + self._low_confidence_rate:
            return IdentityCheckResult(verified=True, confidence=round(rng.uniform(0.5, 0.79), 2))
        return IdentityCheckResult(verified=True, confidence=round(rng.uniform(0.85, 0.99), 2))

    @staticmethod
    def _seeded_rng(document_id: str) -> random.Random:
        digest = hashlib.sha256(document_id.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], byteorder="big", signed=False)
        return random.Random(seed)
