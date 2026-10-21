from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR
from app.orchestrator import Orchestrator
from app.schemas import OnboardingRequest, OnboardingResult
from app.security import LoggingConfigurator


LoggingConfigurator.configure()


app = FastAPI(
    title="Orquestador Agéntico — Onboarding Digital",
    version="0.1.0",
    description=(
        "PoC de orquestador que coordina sub-agentes para onboarding digital bancario. "
        "Las decisiones de aptitud se toman por reglas deterministas, no por LLM."
    ),
)


_orchestrator = Orchestrator()


@app.post("/api/v1/onboarding/start", response_model=OnboardingResult)
def start_onboarding(request: OnboardingRequest) -> OnboardingResult:
    try:
        return _orchestrator.run(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error en orquestación: {exc}") from exc


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


_static_dir: Path = BASE_DIR / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_static_dir / "index.html")
