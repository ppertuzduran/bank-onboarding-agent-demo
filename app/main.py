"""Punto de entrada FastAPI.

Monta en orden:
  1. SecurityHeadersMiddleware (outer)
  2. CORSMiddleware
  3. RateLimitMiddleware
  4. RequestIDMiddleware (innermost — asigna request_id antes de los handlers)

Protege el endpoint `/api/v1/onboarding/start` con `require_api_key`.
Expone `/healthz` (liveness) y `/readyz` (readiness con checks reales).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.audit import AuditEvent, LoggingBootstrap, get_audit_logger
from app.auth import require_api_key
from app.config import BASE_DIR, get_settings
from app.errors import register_exception_handlers
from app.middleware import (
    RateLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)
from app.orchestrator import Orchestrator
from app.schemas import OnboardingRequest, OnboardingResult


logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown. Instancia singletons y los deja en `app.state`."""
    LoggingBootstrap.configure()
    settings = get_settings()
    app.state.settings = settings
    app.state.orchestrator = Orchestrator()
    app.state.audit = get_audit_logger()
    logger.info(
        "Servicio iniciado",
        extra={
            "extra_fields": {
                "service": settings.service_name,
                "version": settings.service_version,
                "environment": settings.environment.value,
                "auth_required": settings.auth_required,
            }
        },
    )
    try:
        yield
    finally:
        logger.info("Servicio detenido")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Orquestador Agéntico — Onboarding Digital Bancario",
        version=settings.service_version,
        description=(
            "PoC de orquestador que coordina sub-agentes para onboarding digital. "
            "Las decisiones de aptitud se toman por reglas deterministas, no por LLM. "
            "Endpoints bajo `/api/` requieren `X-API-Key` fuera del entorno LOCAL."
        ),
        openapi_tags=[
            {"name": "onboarding", "description": "Flujo de onboarding digital."},
            {"name": "health", "description": "Liveness y readiness probes."},
        ],
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    register_exception_handlers(application)

    # Middleware se ejecuta en orden inverso de montaje (último montado = más externo).
    # Montamos: inner first.
    application.add_middleware(RequestIDMiddleware)
    application.add_middleware(
        RateLimitMiddleware,
        requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
    application.add_middleware(
        SecurityHeadersMiddleware,
        is_production=settings.is_production,
    )

    _register_routes(application)
    return application


def _register_routes(application: FastAPI) -> None:
    @application.post(
        "/api/v1/onboarding/start",
        response_model=OnboardingResult,
        status_code=status.HTTP_200_OK,
        tags=["onboarding"],
        summary="Inicia el proceso de onboarding digital",
        responses={
            200: {"description": "Flujo completado o escalado."},
            401: {"description": "API key faltante o inválida."},
            422: {"description": "Payload inválido."},
            429: {"description": "Rate limit excedido."},
            500: {"description": "Error interno."},
        },
    )
    async def start_onboarding(
        payload: OnboardingRequest,
        request: Request,
        _: str = Depends(require_api_key),
    ) -> OnboardingResult:
        audit = request.app.state.audit
        request_id = getattr(request.state, "request_id", None)
        api_key_id = getattr(request.state, "api_key_id", None)

        audit.log(
            AuditEvent.ONBOARDING_STARTED,
            request_id=request_id,
            api_key_id=api_key_id,
            extra={"product": payload.product.value},
        )

        orchestrator: Orchestrator = request.app.state.orchestrator
        result = orchestrator.run(payload)

        event = (
            AuditEvent.ONBOARDING_ESCALATED
            if result.decision.value == "ESCALATED"
            else AuditEvent.ONBOARDING_COMPLETED
        )
        audit.log(
            event,
            request_id=request_id,
            session_id=result.session_id,
            api_key_id=api_key_id,
            decision=result.decision.value,
            extra={"product": payload.product.value},
        )
        return result

    @application.get(
        "/healthz",
        tags=["health"],
        summary="Liveness probe",
    )
    async def healthz() -> JSONResponse:
        settings = get_settings()
        return JSONResponse(
            {
                "status": "ok",
                "service": settings.service_name,
                "version": settings.service_version,
                "environment": settings.environment.value,
            }
        )

    @application.get(
        "/readyz",
        tags=["health"],
        summary="Readiness probe (verifica dependencias)",
    )
    async def readyz() -> JSONResponse:
        settings = get_settings()
        checks: dict[str, str] = {}
        http_status = 200

        # Chroma dir accesible
        try:
            settings.chroma_dir.mkdir(parents=True, exist_ok=True)
            checks["chroma_dir"] = "ok"
        except Exception as exc:
            checks["chroma_dir"] = f"error: {exc.__class__.__name__}"
            http_status = 503

        # SQLite accesible
        try:
            import sqlite3

            with sqlite3.connect(settings.state_db_path) as conn:
                conn.execute("SELECT 1")
            checks["state_db"] = "ok"
        except Exception as exc:
            checks["state_db"] = f"error: {exc.__class__.__name__}"
            http_status = 503

        # Clave de cifrado presente
        checks["fernet_key"] = "ok" if settings.fernet_key else "missing"
        if checks["fernet_key"] != "ok":
            http_status = 503

        return JSONResponse({"status": "ok" if http_status == 200 else "degraded", "checks": checks}, status_code=http_status)

    static_dir: Path = BASE_DIR / "static"
    if static_dir.exists():
        application.mount("/static", StaticFiles(directory=static_dir), name="static")

        @application.get("/", include_in_schema=False)
        async def index() -> FileResponse:
            return FileResponse(static_dir / "index.html")


app: FastAPI = create_app()
