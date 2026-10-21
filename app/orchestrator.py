"""Orquestador: máquina de estados determinista que coordina los sub-agentes."""

from __future__ import annotations

import logging
from enum import StrEnum

from app.agents import DocumentationAgent, IdentityAgent, ResponseAgent, RiskAgent
from app.agents.base import BaseAgent
from app.schemas import (
    AgentOutput,
    Decision,
    OnboardingRequest,
    OnboardingResult,
    PolicySnippet,
    RequiredDocument,
    Status,
)
from app.state import SessionState, SessionStore, get_session_store

logger = logging.getLogger(__name__)


class _Phase(StrEnum):
    IDENTITY = "IDENTITY"
    RISK = "RISK"
    DOCS = "DOCS"
    RESPONSE = "RESPONSE"
    DONE = "DONE"


class Orchestrator:
    """Coordina los sub-agentes.

    Reglas (deterministas):
      - IDENTITY: si requires_escalation, saltar a RESPONSE con decision=ESCALATED.
      - RISK: si requires_escalation (HIGH), saltar a RESPONSE con decision=ESCALATED.
      - DOCS: siempre se ejecuta si no hubo escalación previa.
      - RESPONSE: siempre se ejecuta (determina decision=APPROVED si no hubo escalación).

    Las decisiones de aptitud se toman AQUÍ por reglas simples, no por un LLM:
    cualquier contenido textual (incluido el nombre del cliente) no influye en la
    decisión, lo que mitiga el riesgo de prompt injection.
    """

    def __init__(
        self,
        store: SessionStore | None = None,
        identity_agent: BaseAgent | None = None,
        risk_agent: BaseAgent | None = None,
        documentation_agent: BaseAgent | None = None,
        response_agent: BaseAgent | None = None,
    ) -> None:
        self._store: SessionStore = store or get_session_store()
        self._identity: BaseAgent = identity_agent or IdentityAgent()
        self._risk: BaseAgent = risk_agent or RiskAgent()
        self._docs: BaseAgent = documentation_agent or DocumentationAgent()
        self._response: BaseAgent = response_agent or ResponseAgent()

    def run(self, request: OnboardingRequest) -> OnboardingResult:
        state = self._store.create(request)
        logger.info("Sesión creada %s para producto %s", state.session_id, request.product.value)

        decision: Decision = Decision.APPROVED
        phase = _Phase.IDENTITY

        while phase != _Phase.DONE:
            if phase == _Phase.IDENTITY:
                trace = self._run_agent(state, self._identity)
                if trace.requires_escalation:
                    decision = Decision.ESCALATED
                    phase = _Phase.RESPONSE
                else:
                    phase = _Phase.RISK

            elif phase == _Phase.RISK:
                trace = self._run_agent(state, self._risk)
                if trace.requires_escalation:
                    decision = Decision.ESCALATED
                    phase = _Phase.RESPONSE
                else:
                    phase = _Phase.DOCS

            elif phase == _Phase.DOCS:
                self._run_agent(state, self._docs)
                phase = _Phase.RESPONSE

            elif phase == _Phase.RESPONSE:
                self._store.put_scratch(state.session_id, "decision", decision.value)
                state = self._store.get(state.session_id) or state
                self._run_agent(state, self._response)
                phase = _Phase.DONE

        final_status = Status.ESCALATED if decision == Decision.ESCALATED else Status.COMPLETED
        state = self._store.set_status(state.session_id, final_status)
        return self._build_result(state, decision)

    def _run_agent(self, state: SessionState, agent: BaseAgent) -> AgentOutput:
        fresh = self._store.get(state.session_id) or state
        trace = agent.run(fresh)
        self._store.append_step(state.session_id, trace)
        logger.info(
            "Sesión %s | %s | escalate=%s",
            state.session_id,
            trace.agent,
            trace.requires_escalation,
        )
        return trace

    @staticmethod
    def _build_result(state: SessionState, decision: Decision) -> OnboardingResult:
        docs_step = next((s for s in state.steps if s.agent == "documentation_agent"), None)
        response_step = next((s for s in state.steps if s.agent == "response_agent"), None)

        required_docs: list[RequiredDocument] = []
        snippets: list[PolicySnippet] = []
        if docs_step is not None:
            required_docs = [
                RequiredDocument(**d) for d in docs_step.output.get("required_documents", [])
            ]
            snippets = [
                PolicySnippet(**s) for s in docs_step.output.get("policy_snippets", [])
            ]

        message = ""
        if response_step is not None:
            message = str(response_step.output.get("message_to_client", ""))

        escalation_proposal: str | None = None
        if decision == Decision.ESCALATED:
            escalation_proposal = (
                "Derivar al equipo de cumplimiento. Solicitar verificación presencial "
                "o documentación adicional según el motivo registrado en los pasos."
            )

        status = Status.ESCALATED if decision == Decision.ESCALATED else Status.COMPLETED

        return OnboardingResult(
            session_id=state.session_id,
            status=status,
            decision=decision,
            message_to_client=message,
            required_documents=required_docs,
            policy_snippets=snippets,
            steps=list(state.steps),
            escalation_proposal=escalation_proposal,
        )
