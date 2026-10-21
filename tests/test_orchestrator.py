"""Tests del orquestador con sub-agentes falsos (sin RAG real).

Validamos la máquina de estados: cada ruta (approved / escalated por identity /
escalated por risk) produce la salida correcta y las trazas se registran.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.orchestrator import Orchestrator
from app.schemas import (
    AgentOutput,
    Decision,
    IdentityCheckResult,
    OnboardingRequest,
    Product,
    RiskCheckResult,
    RiskLevel,
    Status,
)


class _FakeIdentity(BaseAgent):
    name = "identity_agent"

    def __init__(self, verified: bool, confidence: float) -> None:
        self._result = IdentityCheckResult(verified=verified, confidence=confidence)

    def run(self, state):
        requires_escalation = (not self._result.verified) or (self._result.confidence < 0.8)
        return AgentOutput(
            agent=self.name,
            output=self._result.model_dump(),
            requires_escalation=requires_escalation,
            reason="forced" if requires_escalation else None,
        )


class _FakeRisk(BaseAgent):
    name = "risk_agent"

    def __init__(self, level: RiskLevel) -> None:
        self._level = level

    def run(self, state):
        res = RiskCheckResult(risk_level=self._level, matches=["TEST"] if self._level == RiskLevel.HIGH else [])
        return AgentOutput(
            agent=self.name,
            output=res.model_dump(),
            requires_escalation=self._level == RiskLevel.HIGH,
            reason="forced" if self._level == RiskLevel.HIGH else None,
        )


class _FakeDocs(BaseAgent):
    name = "documentation_agent"

    def run(self, state):
        return AgentOutput(
            agent=self.name,
            output={
                "required_documents": [{"name": "Cédula", "mandatory": True, "reason": None}],
                "policy_snippets": [],
            },
        )


class _FakeResponse(BaseAgent):
    name = "response_agent"

    def run(self, state):
        decision = state.scratch.get("decision", "APPROVED")
        return AgentOutput(
            agent=self.name,
            output={"message_to_client": f"test:{decision}", "decision": decision},
        )


def _request() -> OnboardingRequest:
    return OnboardingRequest(
        prospect_name="Juan Perez",
        document_id="1234567890",
        product=Product.CUENTA_AHORROS,
    )


def test_happy_path_approved() -> None:
    orch = Orchestrator(
        identity_agent=_FakeIdentity(verified=True, confidence=0.95),
        risk_agent=_FakeRisk(RiskLevel.LOW),
        documentation_agent=_FakeDocs(),
        response_agent=_FakeResponse(),
    )
    result = orch.run(_request())
    assert result.status == Status.COMPLETED
    assert result.decision == Decision.APPROVED
    agents_run = [s.agent for s in result.steps]
    assert agents_run == ["identity_agent", "risk_agent", "documentation_agent", "response_agent"]
    assert "APPROVED" in result.message_to_client


def test_escalates_on_low_identity_confidence() -> None:
    orch = Orchestrator(
        identity_agent=_FakeIdentity(verified=True, confidence=0.5),
        risk_agent=_FakeRisk(RiskLevel.LOW),
        documentation_agent=_FakeDocs(),
        response_agent=_FakeResponse(),
    )
    result = orch.run(_request())
    assert result.status == Status.ESCALATED
    assert result.decision == Decision.ESCALATED
    assert [s.agent for s in result.steps] == ["identity_agent", "response_agent"]
    assert result.escalation_proposal is not None


def test_escalates_on_high_risk() -> None:
    orch = Orchestrator(
        identity_agent=_FakeIdentity(verified=True, confidence=0.95),
        risk_agent=_FakeRisk(RiskLevel.HIGH),
        documentation_agent=_FakeDocs(),
        response_agent=_FakeResponse(),
    )
    result = orch.run(_request())
    assert result.status == Status.ESCALATED
    assert result.decision == Decision.ESCALATED
    assert [s.agent for s in result.steps] == ["identity_agent", "risk_agent", "response_agent"]


def test_medium_risk_does_not_escalate() -> None:
    orch = Orchestrator(
        identity_agent=_FakeIdentity(verified=True, confidence=0.9),
        risk_agent=_FakeRisk(RiskLevel.MEDIUM),
        documentation_agent=_FakeDocs(),
        response_agent=_FakeResponse(),
    )
    result = orch.run(_request())
    assert result.status == Status.COMPLETED
    assert result.decision == Decision.APPROVED
