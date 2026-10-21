"""Mock de consulta a listas de riesgo (OFAC, PEP, listas internas).

Determinista por `(name, document_id)`. Devuelve un `RiskCheckResult` validado por Pydantic.
"""

from __future__ import annotations

import hashlib
import random

from app.schemas import RiskCheckResult, RiskLevel


class RiskListChecker:
    """Simula una consulta a listas de riesgo externas."""

    _SYNTHETIC_LISTS: tuple[str, ...] = (
        "OFAC-SDN",
        "PEP-NAL",
        "ONU-SANCIONES",
        "LISTA-INTERNA-BANCO",
    )

    def __init__(self, high_risk_rate: float = 0.1, medium_risk_rate: float = 0.2) -> None:
        total = high_risk_rate + medium_risk_rate
        if not 0.0 <= total <= 1.0:
            raise ValueError("high_risk_rate + medium_risk_rate debe estar en [0, 1]")
        self._high_risk_rate: float = high_risk_rate
        self._medium_risk_rate: float = medium_risk_rate

    def execute(self, name: str, document_id: str) -> RiskCheckResult:
        rng = self._seeded_rng(name, document_id)
        roll = rng.random()
        if roll < self._high_risk_rate:
            return RiskCheckResult(
                risk_level=RiskLevel.HIGH,
                matches=[rng.choice(self._SYNTHETIC_LISTS)],
            )
        if roll < self._high_risk_rate + self._medium_risk_rate:
            return RiskCheckResult(risk_level=RiskLevel.MEDIUM, matches=[])
        return RiskCheckResult(risk_level=RiskLevel.LOW, matches=[])

    @staticmethod
    def _seeded_rng(name: str, document_id: str) -> random.Random:
        key = f"{name.lower().strip()}|{document_id}".encode("utf-8")
        digest = hashlib.sha256(key).digest()
        seed = int.from_bytes(digest[:8], byteorder="big", signed=False)
        return random.Random(seed)
