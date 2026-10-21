from __future__ import annotations

from app.agents.base import BaseAgent
from app.config import get_settings
from app.rag.retriever import ChromaRetriever, get_retriever
from app.schemas import AgentOutput, PolicySnippet
from app.state import SessionState
from app.tools import DocumentationPreparer


class DocumentationAgent(BaseAgent):
    """Devuelve información personalizada según el perfil (producto) del cliente.

    Combina dos fuentes:
      1. `DocumentationPreparer` — requisitos documentales obligatorios por producto.
      2. RAG sobre políticas internas — chunks relevantes de política bancaria
         filtrados por producto como metadata.

    Si no hay chunks relevantes (score < umbral), no inventa — devuelve lista vacía
    y la razón "sin contexto relevante".
    """

    name: str = "documentation_agent"
    _SCORE_THRESHOLD: float = 0.25

    def __init__(
        self,
        preparer: DocumentationPreparer | None = None,
        retriever: ChromaRetriever | None = None,
    ) -> None:
        self._preparer: DocumentationPreparer = preparer or DocumentationPreparer()
        self._retriever: ChromaRetriever = retriever or get_retriever()
        self._top_k: int = get_settings().retrieval_top_k

    def run(self, state: SessionState) -> AgentOutput:
        product = state.payload.product
        prep = self._preparer.execute(product=product)

        query = f"Requisitos y política para {product.value} en apertura de cliente"
        try:
            hits = self._retriever.query(
                text=query,
                top_k=self._top_k,
                where={"product": product.value},
            )
        except Exception as exc:
            return AgentOutput(
                agent=self.name,
                output={
                    "required_documents": [d.model_dump() for d in prep.required_documents],
                    "policy_snippets": [],
                    "retrieval_error": str(exc),
                },
                requires_escalation=False,
                reason="Fallo recuperando política RAG; se devuelven requisitos base.",
            )

        relevant = [h for h in hits if h.score >= self._SCORE_THRESHOLD]
        snippets = [
            PolicySnippet(
                document=h.document,
                section=h.section,
                text=h.text,
                score=h.score,
            )
            for h in relevant
        ]

        reason: str | None = None
        if not snippets:
            reason = "Sin contexto relevante en política RAG; se devuelven requisitos base."

        return AgentOutput(
            agent=self.name,
            output={
                "required_documents": [d.model_dump() for d in prep.required_documents],
                "policy_snippets": [s.model_dump() for s in snippets],
            },
            requires_escalation=False,
            reason=reason,
        )
