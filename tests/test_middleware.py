from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.middleware import (
    REQUEST_ID_HEADER,
    RateLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RateLimitMiddleware, requests=3, window_seconds=60)
    app.add_middleware(SecurityHeadersMiddleware, is_production=True)

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/api/v1/dummy")
    async def dummy() -> JSONResponse:
        return JSONResponse({"ok": True})

    return app


def test_security_headers_present() -> None:
    client = TestClient(_make_app())
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in res.headers
    assert res.headers["Referrer-Policy"] == "no-referrer"
    assert "Strict-Transport-Security" in res.headers


def test_api_responses_are_not_cached() -> None:
    client = TestClient(_make_app())
    res = client.get("/api/v1/dummy")
    assert res.headers["Cache-Control"] == "no-store"


def test_request_id_generated_and_echoed() -> None:
    client = TestClient(_make_app())
    res = client.get("/healthz")
    assert REQUEST_ID_HEADER in res.headers
    assert len(res.headers[REQUEST_ID_HEADER]) >= 8


def test_request_id_respects_valid_incoming_header() -> None:
    client = TestClient(_make_app())
    res = client.get("/healthz", headers={REQUEST_ID_HEADER: "abc-123-xyz"})
    assert res.headers[REQUEST_ID_HEADER] == "abc-123-xyz"


def test_request_id_rejects_invalid_incoming_header() -> None:
    client = TestClient(_make_app())
    res = client.get("/healthz", headers={REQUEST_ID_HEADER: "<script>"})
    assert res.headers[REQUEST_ID_HEADER] != "<script>"


def test_rate_limit_blocks_after_capacity_on_api_paths() -> None:
    client = TestClient(_make_app())
    for _ in range(3):
        assert client.get("/api/v1/dummy").status_code == 200
    throttled = client.get("/api/v1/dummy")
    assert throttled.status_code == 429
    assert "Retry-After" in throttled.headers
    body = throttled.json()
    assert body["status"] == 429
    assert body["title"] == "Too Many Requests"


def test_rate_limit_does_not_affect_non_api_paths() -> None:
    client = TestClient(_make_app())
    for _ in range(10):
        assert client.get("/healthz").status_code == 200
