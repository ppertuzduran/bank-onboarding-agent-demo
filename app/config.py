"""Configuración centralizada validada por Pydantic.

Lee de variables de entorno y `.env`. Nunca hardcodear secretos.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR: Path = Path(__file__).resolve().parent.parent


class Environment(str, Enum):
    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Configuración de la aplicación.

    Todos los secretos (API_KEY, FERNET_KEY) deben venir de variables de entorno
    o de un gestor de secretos (p. ej., AWS Secrets Manager) en entornos superiores.
    """

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Entorno
    environment: Environment = Field(default=Environment.LOCAL)
    service_name: str = Field(default="onboarding-orchestrator")
    service_version: str = Field(default="0.2.0")

    # Secretos
    fernet_key: str = Field(default="", min_length=0, description="Clave Fernet urlsafe-base64")
    api_key: str = Field(default="", description="API key compartida; vacía deshabilita auth (solo LOCAL)")

    # Rutas de datos
    data_dir: Path = Field(default=BASE_DIR / "data")
    docs_plain_dir: Path = Field(default=BASE_DIR / "data" / "synthetic_docs")
    docs_encrypted_dir: Path = Field(default=BASE_DIR / "data" / "encrypted")
    chroma_dir: Path = Field(default=BASE_DIR / "data" / "chroma")
    state_db_path: Path = Field(default=BASE_DIR / "data" / "state.sqlite")

    # Umbrales de orquestación
    identity_confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    retrieval_top_k: int = Field(default=3, ge=1, le=20)

    # RAG local
    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    chroma_collection: str = Field(default="bank_policies")

    # CORS — coma-separado. En LOCAL permitimos la UI; en PROD exige lista explícita.
    cors_allowed_origins: str = Field(
        default="http://127.0.0.1:8000,http://localhost:8000"
    )

    # Rate limiting (token bucket por IP + por API key)
    rate_limit_requests: int = Field(default=30, ge=1, description="Peticiones por ventana")
    rate_limit_window_seconds: int = Field(default=60, ge=1, description="Tamaño de ventana en segundos")

    # Timeouts
    request_timeout_seconds: int = Field(default=30, ge=1, le=120)

    # AWS (Fase 2)
    aws_region: str = Field(default="")
    aws_profile: str = Field(default="")
    bedrock_embedding_model: str = Field(default="amazon.titan-embed-text-v2:0")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def auth_required(self) -> bool:
        """La autenticación es obligatoria fuera de LOCAL o cuando hay API key configurada."""
        return self.is_production or self.environment == Environment.STAGING or bool(self.api_key)

    def ensure_dirs(self) -> None:
        for directory in (
            self.data_dir,
            self.docs_plain_dir,
            self.docs_encrypted_dir,
            self.chroma_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
