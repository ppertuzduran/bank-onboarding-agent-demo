"""Tests end-to-end del endpoint con el orquestador real pero con RAG stubbed.

Reemplaza el `documentation_agent` por un fake para no requerir el modelo
de embeddings descargado.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.agents.base import BaseAgent
from app.config import get_settings
from app.schemas import AgentOutput


class _FakeDocsAgent(BaseAgent):
    name = "documentation_agent"

    def run(self, state):
        return AgentOutput(
            agent=self.name,
            output={
                "required_documents": [{"name": "Cédula", "mandatory": True, "reason": None}],
                "policy_snippets": [],
            },
        )


@pytest.fixture()
def client() -> TestClient:
    os.environ["API_KEY"] = "test-key"
    os.environ["ENVIRONMENT"] = "staging"
    get_settings.cache_clear()

    from app.main import create_app
    from app.orchestrator import Orchestrator

    app = create_app()
    app.state.orchestrator = Orchestrator(documentation_agent=_FakeDocsAgent())
    with TestClient(app) as c:
        yield c


def _valid_payload() -> dict:
    return {
        "prospect_name": "Juan Perez",
        "document_id": "1712345678",
        "product": "cuenta_ahorros",
    }


def test_endpoint_requires_api_key(client: TestClient) -> None:
    res = client.post("/api/v1/onboarding/start", json=_valid_payload())
    assert res.status_code == 401
    assert res.headers.get("content-type", "").startswith("application/problem+json")
    body = res.json()
    assert body["status"] == 401
    assert "request_id" in body


def test_endpoint_rejects_bad_api_key(client: TestClient) -> None:
    res = client.post(
        "/api/v1/onboarding/start",
        json=_valid_payload(),
        headers={"X-API-Key": "wrong"},
    )
    assert res.status_code == 401


def test_endpoint_rejects_malformed_payload(client: TestClient) -> None:
    bad = {"prospect_name": "Juan 2", "document_id": "abc", "product": "credito_hipotecario"}
    res = client.post(
        "/api/v1/onboarding/start",
        json=bad,
        headers={"X-API-Key": "test-key"},
    )
    assert res.status_code == 422
    body = res.json()
    assert body["title"] == "Unprocessable Entity"
    assert isinstance(body["errors"], list) and len(body["errors"]) > 0


def test_endpoint_happy_path_returns_result(client: TestClient) -> None:
    res = client.post(
        "/api/v1/onboarding/start",
        json=_valid_payload(),
        headers={"X-API-Key": "test-key"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["decision"] in {"APPROVED", "ESCALATED", "REJECTED"}
    assert body["session_id"]
    assert "X-Request-ID" in res.headers
    assert res.headers["Cache-Control"] == "no-store"


def test_healthz_is_public(client: TestClient) -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["service"] == "onboarding-orchestrator"


def test_readyz_reports_checks(client: TestClient) -> None:
    res = client.get("/readyz")
    assert res.status_code in (200, 503)
    body = res.json()
    assert "checks" in body
    assert "chroma_dir" in body["checks"]
    assert "state_db" in body["checks"]
    assert "fernet_key" in body["checks"]
