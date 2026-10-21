from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_PRODUCTS: set[str] = {
    "cuenta_ahorros",
    "cuenta_corriente",
    "tarjeta_credito",
    "credito_consumo",
}


class Product(StrEnum):
    CUENTA_AHORROS = "cuenta_ahorros"
    CUENTA_CORRIENTE = "cuenta_corriente"
    TARJETA_CREDITO = "tarjeta_credito"
    CREDITO_CONSUMO = "credito_consumo"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Status(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"


class Decision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class OnboardingRequest(BaseModel):
    """Payload de entrada del endpoint. Valida y sanitiza en el borde."""

    model_config = ConfigDict(str_strip_whitespace=True)

    prospect_name: str = Field(min_length=2, max_length=120)
    document_id: str = Field(min_length=5, max_length=20)
    product: Product

    @field_validator("prospect_name")
    @classmethod
    def _name_only_letters(cls, value: str) -> str:
        if not all(ch.isalpha() or ch.isspace() for ch in value):
            raise ValueError("prospect_name solo admite letras y espacios")
        return value

    @field_validator("document_id")
    @classmethod
    def _doc_digits_only(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("document_id debe contener solo dígitos")
        return value


class IdentityCheckResult(BaseModel):
    verified: bool
    confidence: float = Field(ge=0.0, le=1.0)


class RiskCheckResult(BaseModel):
    risk_level: RiskLevel
    matches: list[str] = Field(default_factory=list)


class RequiredDocument(BaseModel):
    name: str
    mandatory: bool = True
    reason: str | None = None


class DocumentPreparationResult(BaseModel):
    product: Product
    required_documents: list[RequiredDocument]


class PolicySnippet(BaseModel):
    document: str
    section: str
    text: str
    score: float = Field(ge=0.0, le=1.0)


class AgentOutput(BaseModel):
    agent: str
    output: dict[str, Any]
    requires_escalation: bool = False
    reason: str | None = None


class OnboardingResult(BaseModel):
    session_id: str
    status: Status
    decision: Decision
    message_to_client: str
    required_documents: list[RequiredDocument] = Field(default_factory=list)
    policy_snippets: list[PolicySnippet] = Field(default_factory=list)
    steps: list[AgentOutput] = Field(default_factory=list)
    escalation_proposal: str | None = None


class EvaluationQuestion(BaseModel):
    """Pregunta sintética para medir hit@k."""

    question: str
    expected_document: str
    expected_section: str
    tags: list[str] = Field(default_factory=list)


class HitAtKReport(BaseModel):
    k_values: list[int]
    total_questions: int
    hits_at: dict[int, int]
    recall_at: dict[int, float]
    per_question: list[dict[str, Any]] = Field(default_factory=list)

    def summary(self) -> str:
        parts: list[str] = []
        for k in self.k_values:
            parts.append(f"hit@{k}={self.hits_at[k]}/{self.total_questions} ({self.recall_at[k]:.1%})")
        return " | ".join(parts)


DecisionLiteral = Literal["APPROVED", "REJECTED", "ESCALATED"]
