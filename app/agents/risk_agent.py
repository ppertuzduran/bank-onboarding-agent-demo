from __future__ import annotations

from app.agents.base import BaseAgent
from app.schemas import AgentOutput, RiskLevel
from app.state import SessionState
from app.tools import RiskListChecker


class RiskAgent(BaseAgent):
    """Consulta listas de riesgo.

    Decisión de escalación: `risk_level == HIGH`.
    `MEDIUM` continúa el flujo pero queda registrado en el estado.
    """

    name: str = "risk_agent"

    def __init__(self, checker: RiskListChecker | None = None) -> None:
        self._checker: RiskListChecker = checker or RiskListChecker()

    def run(self, state: SessionState) -> AgentOutput:
        result = self._checker.execute(
            name=state.payload.prospect_name,
            document_id=state.payload.document_id,
        )
        requires_escalation = result.risk_level == RiskLevel.HIGH
        reason: str | None = None
        if requires_escalation:
            matches = ", ".join(result.matches) if result.matches else "lista no especificada"
            reason = f"Coincidencia en lista de alto riesgo ({matches})."
        return AgentOutput(
            agent=self.name,
            output=result.model_dump(),
            requires_escalation=requires_escalation,
            reason=reason,
        )
