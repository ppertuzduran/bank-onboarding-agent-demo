"""Autenticación por API Key.

Usa comparación en tiempo constante (`secrets.compare_digest`) para evitar
timing attacks. El API key se envía en el header `X-API-Key`.

En Fase AWS, el API Key debería leerse de Secrets Manager y rotarse
periódicamente. Para producción real, considerar OAuth2/OIDC con JWT firmados,
mTLS entre servicios internos o AWS Cognito.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings


_API_KEY_HEADER: str = "X-API-Key"


class APIKeyAuth:
    """Dependency callable que valida el API key.

    Si `settings.auth_required` es False (p. ej., entorno LOCAL sin API_KEY
    configurada), permite el request pero deja constancia en el estado del
    request para auditoría.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings: Settings = settings

    def __call__(
        self,
        request: Request,
        x_api_key: str | None = Header(default=None, alias=_API_KEY_HEADER),
    ) -> str:
        if not self._settings.auth_required:
            request.state.auth_mode = "anonymous_local"
            request.state.api_key_id = "anonymous"
            return "anonymous"

        if not x_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Falta header X-API-Key",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        if not self._constant_time_equals(x_api_key, self._settings.api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key inválida",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        request.state.auth_mode = "api_key"
        # No se guarda el key completo en el estado; solo un identificador corto
        # para auditoría. En producción, correlacionar con una tabla de API keys.
        request.state.api_key_id = x_api_key[:4] + "***"
        return request.state.api_key_id

    @staticmethod
    def _constant_time_equals(provided: str, expected: str) -> bool:
        if not expected:
            return False
        return secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias=_API_KEY_HEADER),
    settings: Settings = Depends(get_settings),
) -> str:
    """FastAPI dependency expuesta como función para registrar en los endpoints."""
    auth = APIKeyAuth(settings)
    return auth(request=request, x_api_key=x_api_key)
