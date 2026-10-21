"""Response agent: compone el mensaje final al cliente.

Fase Local: stub determinístico con plantillas en español (sin LLM — no hay cuota
de Bedrock en la cuenta). En Fase AWS se reemplaza por un cliente de Bedrock que
reciba el estado como contexto estructurado y produzca el texto final.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.schemas import AgentOutput, Decision
from app.state import SessionState


class ResponseAgent(BaseAgent):
    name: str = "response_agent"

    def run(self, state: SessionState) -> AgentOutput:
        decision = state.scratch.get("decision", Decision.ESCALATED)
        if isinstance(decision, str):
            decision = Decision(decision)

        name = state.payload.prospect_name
        product = state.payload.product.value.replace("_", " ")

        if decision == Decision.APPROVED:
            message = self._render_approved(name=name, product=product, state=state)
        elif decision == Decision.REJECTED:
            message = self._render_rejected(name=name, product=product, state=state)
        else:
            message = self._render_escalated(name=name, product=product, state=state)

        return AgentOutput(
            agent=self.name,
            output={"message_to_client": message, "decision": decision.value},
        )

    @staticmethod
    def _render_approved(name: str, product: str, state: SessionState) -> str:
        docs_step = next(
            (s for s in state.steps if s.agent == "documentation_agent"), None
        )
        docs: list[str] = []
        if docs_step is not None:
            raw_docs = docs_step.output.get("required_documents", [])
            docs = [d.get("name", "") for d in raw_docs if d.get("mandatory", True)]
        docs_text = "\n".join(f"  - {d}" for d in docs) if docs else "  (sin requisitos adicionales)"
        return (
            f"Hola {name}, hemos pre-aprobado tu solicitud para {product}. "
            f"Para completar el proceso, necesitamos los siguientes documentos:\n"
            f"{docs_text}\n\n"
            f"Nuestro equipo te contactará dentro de las próximas 24 horas hábiles."
        )

    @staticmethod
    def _render_rejected(name: str, product: str, state: SessionState) -> str:
        return (
            f"Hola {name}, lamentablemente no podemos continuar con la apertura "
            f"de {product} en este momento. Si consideras que esto es un error, "
            f"por favor contáctanos y revisaremos tu caso con un asesor."
        )

    @staticmethod
    def _render_escalated(name: str, product: str, state: SessionState) -> str:
        reasons: list[str] = []
        for step in state.steps:
            if step.requires_escalation and step.reason:
                reasons.append(f"- {step.agent}: {step.reason}")
        reasons_text = "\n".join(reasons) if reasons else "- Verificación adicional requerida."
        return (
            f"Hola {name}, tu solicitud para {product} requiere una revisión "
            f"adicional por parte de nuestro equipo de cumplimiento. "
            f"Motivo(s):\n{reasons_text}\n\n"
            f"Un asesor humano te contactará para completar la verificación."
        )
