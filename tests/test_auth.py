from __future__ import annotations

import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import APIKeyAuth
from app.config import get_settings


class _StubRequest:
    def __init__(self) -> None:
        self.state = type("S", (), {})()


def _settings_with(api_key: str, env: str = "staging"):
    os.environ["API_KEY"] = api_key
    os.environ["ENVIRONMENT"] = env
    get_settings.cache_clear()
    return get_settings()


def test_rejects_missing_api_key_when_required() -> None:
    settings = _settings_with(api_key="s3cret-key", env="staging")
    auth = APIKeyAuth(settings)
    with pytest.raises(HTTPException) as exc:
        auth(request=_StubRequest(), x_api_key=None)
    assert exc.value.status_code == 401


def test_rejects_wrong_api_key() -> None:
    settings = _settings_with(api_key="s3cret-key", env="staging")
    auth = APIKeyAuth(settings)
    with pytest.raises(HTTPException) as exc:
        auth(request=_StubRequest(), x_api_key="not-the-key")
    assert exc.value.status_code == 401


def test_accepts_correct_api_key() -> None:
    settings = _settings_with(api_key="s3cret-key", env="staging")
    auth = APIKeyAuth(settings)
    req = _StubRequest()
    result = auth(request=req, x_api_key="s3cret-key")
    assert result.endswith("***")
    assert req.state.auth_mode == "api_key"


def test_local_without_api_key_allows_anonymous() -> None:
    settings = _settings_with(api_key="", env="local")
    auth = APIKeyAuth(settings)
    req = _StubRequest()
    result = auth(request=req, x_api_key=None)
    assert result == "anonymous"
    assert req.state.auth_mode == "anonymous_local"
