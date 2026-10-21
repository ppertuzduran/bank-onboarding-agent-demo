"""Exception handlers globales siguiendo RFC 7807 (Problem Details for HTTP APIs).

Normaliza todas las respuestas de error del API al mismo formato
`application/problem+json`, nunca filtra stack traces hacia el cliente,
y registra el error con `request_id` para correlación.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse


logger = logging.getLogger("app.errors")


class ProblemDetails(BaseModel):
    """Representación RFC 7807 de un error HTTP."""

    type: str = Field(default="about:blank")
    title: str
    status: int
    detail: str
    instance: str | None = None
    request_id: str | None = None
    errors: list[dict] | None = None


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los handlers globales. Llamar durante el bootstrap de la app."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        problem = ProblemDetails(
            title=_default_title(exc.status_code),
            status=exc.status_code,
            detail=str(exc.detail),
            instance=request.url.path,
            request_id=_request_id(request),
        )
        logger.info(
            "HTTPException status=%d path=%s request_id=%s",
            exc.status_code,
            request.url.path,
            problem.request_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
            headers=exc.headers or {},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        safe_errors: list[dict] = []
        for error in exc.errors():
            safe_errors.append(
                {
                    "loc": [str(part) for part in error.get("loc", [])],
                    "msg": str(error.get("msg", "")),
                    "type": str(error.get("type", "")),
                }
            )
        problem = ProblemDetails(
            type="https://httpstatuses.io/422",
            title="Unprocessable Entity",
            status=422,
            detail="La solicitud contiene datos inválidos.",
            instance=request.url.path,
            request_id=_request_id(request),
            errors=safe_errors,
        )
        logger.info(
            "Validation error path=%s request_id=%s n_errors=%d",
            request.url.path,
            problem.request_id,
            len(safe_errors),
        )
        return JSONResponse(
            status_code=422,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # No se filtra `str(exc)` al cliente para evitar information disclosure.
        # El detalle completo queda en logs internos (con PII redactada).
        request_id = _request_id(request)
        logger.exception(
            "Unhandled exception path=%s request_id=%s", request.url.path, request_id
        )
        problem = ProblemDetails(
            type="about:blank",
            title="Internal Server Error",
            status=500,
            detail="Error interno. El equipo ha sido notificado.",
            instance=request.url.path,
            request_id=request_id,
        )
        return JSONResponse(
            status_code=500,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )


_DEFAULT_TITLES: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}


def _default_title(status_code: int) -> str:
    return _DEFAULT_TITLES.get(status_code, "Error")
