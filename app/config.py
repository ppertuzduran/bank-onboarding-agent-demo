from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR: Path = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Configuración validada por Pydantic. Lee de .env y variables de entorno."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    fernet_key: str = Field(default="", description="Clave Fernet (base64 urlsafe, 32 bytes)")

    data_dir: Path = Field(default=BASE_DIR / "data")
    docs_plain_dir: Path = Field(default=BASE_DIR / "data" / "synthetic_docs")
    docs_encrypted_dir: Path = Field(default=BASE_DIR / "data" / "encrypted")
    chroma_dir: Path = Field(default=BASE_DIR / "data" / "chroma")
    state_db_path: Path = Field(default=BASE_DIR / "data" / "state.sqlite")

    identity_confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    retrieval_top_k: int = Field(default=3, ge=1, le=20)

    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    chroma_collection: str = Field(default="bank_policies")

    aws_region: str = Field(default="")
    aws_profile: str = Field(default="")
    bedrock_embedding_model: str = Field(default="amazon.titan-embed-text-v2:0")

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
