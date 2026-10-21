"""Middlewares de seguridad y observabilidad.

Orden recomendado de montaje (de más externo a más interno):
    1. SecurityHeadersMiddleware   — endurece respuestas (HSTS, CSP, etc.).
    2. RequestIDMiddleware         — correlation ID por request.
    3. RateLimitMiddleware         — token-bucket in-memory por IP/API key.
    4. CORSMiddleware (FastAPI)    — montado desde main.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

REQUEST_ID_HEADER: str = "X-Request-ID"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Añade security headers alineados con OWASP Secure Headers Project.

    - HSTS: fuerza HTTPS (efectivo solo tras servir sobre TLS; inofensivo en local).
    - X-Content-Type-Options: evita MIME sniffing.
    - X-Frame-Options: previene clickjacking.
    - Referrer-Policy: no fugar URLs internas.
    - Permissions-Policy: deshabilita sensores no usados.
    - Content-Security-Policy: estricta para la UI estática.
    - Cache-Control: no cachear respuestas de API.
    """

    _API_PATH_PREFIX: str = "/api/"

    def __init__(self, app: ASGIApp, is_production: bool) -> None:
        super().__init__(app)
        self._is_production: bool = is_production

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        if self._is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith(self._API_PATH_PREFIX):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Asigna un UUID por request y lo propaga en response y en `request.state`.

    Si el cliente envía `X-Request-ID`, se respeta (útil para trazabilidad
    end-to-end entre servicios); en caso contrario se genera uno.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming and self._is_valid_id(incoming) else str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @staticmethod
    def _is_valid_id(value: str) -> bool:
        if not (8 <= len(value) <= 64):
            return False
        return all(ch.isalnum() or ch in "-_" for ch in value)


@dataclass
class _Bucket:
    tokens: float
    last_refill: float
    lock: threading.Lock = field(default_factory=threading.Lock)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket por clave (IP o API key).

    Capacidad = `requests`. Rellenado continuo a tasa `requests / window_seconds`.
    Solo aplica a rutas bajo `/api/`. Devuelve 429 con `Retry-After` cuando
    se agota.

    En producción con múltiples réplicas, reemplazar por Redis/ElastiCache
    (Lua script o librería como `redis-cell`).
    """

    def __init__(
        self,
        app: ASGIApp,
        requests: int,
        window_seconds: int,
        protected_path_prefix: str = "/api/",
    ) -> None:
        super().__init__(app)
        self._capacity: float = float(requests)
        self._refill_per_second: float = float(requests) / float(window_seconds)
        self._window_seconds: int = window_seconds
        self._protected_prefix: str = protected_path_prefix
        self._buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(tokens=self._capacity, last_refill=time.monotonic()))
        self._registry_lock: threading.Lock = threading.Lock()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not request.url.path.startswith(self._protected_prefix):
            return await call_next(request)

        key = self._identify(request)
        bucket = self._get_bucket(key)
        allowed, retry_after = self._consume(bucket)

        if not allowed:
            payload = {
                "type": "about:blank",
                "title": "Too Many Requests",
                "status": 429,
                "detail": "Has superado el límite de peticiones. Reintenta más tarde.",
                "retry_after_seconds": retry_after,
            }
            return JSONResponse(
                status_code=429,
                content=payload,
                headers={"Retry-After": str(retry_after)},
                media_type="application/problem+json",
            )

        return await call_next(request)

    def _identify(self, request: Request) -> str:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"key:{api_key[:8]}"
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    def _get_bucket(self, key: str) -> _Bucket:
        with self._registry_lock:
            return self._buckets[key]

    def _consume(self, bucket: _Bucket) -> tuple[bool, int]:
        with bucket.lock:
            now = time.monotonic()
            elapsed = now - bucket.last_refill
            bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill_per_second)
            bucket.last_refill = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, 0
            needed = 1.0 - bucket.tokens
            retry_after = max(1, int(needed / self._refill_per_second) + 1)
            return False, retry_after
