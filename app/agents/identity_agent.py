from __future__ import annotations

from app.agents.base import BaseAgent
from app.config import get_settings
from app.schemas import AgentOutput
from app.state import SessionState
from app.tools import IdentityVerifier


class IdentityAgent(BaseAgent):
    """Verifica la identidad usando la tool `IdentityVerifier`.

    Decisión de escalación: `verified == False` o `confidence < umbral`.
    """

    name: str = "identity_agent"

    def __init__(self, verifier: IdentityVerifier | None = None) -> None:
        self._verifier: IdentityVerifier = verifier or IdentityVerifier()
        self._threshold: float = get_settings().identity_confidence_threshold

    def run(self, state: SessionState) -> AgentOutput:
        result = self._verifier.execute(state.payload.document_id)
        requires_escalation = (not result.verified) or (result.confidence < self._threshold)
        reason: str | None = None
        if not result.verified:
            reason = "La identidad no pudo ser verificada por el proveedor."
        elif result.confidence < self._threshold:
            reason = (
                f"Confianza de verificación {result.confidence:.2f} por debajo "
                f"del umbral {self._threshold:.2f}."
            )
        return AgentOutput(
            agent=self.name,
            output=result.model_dump(),
            requires_escalation=requires_escalation,
            reason=reason,
        )
