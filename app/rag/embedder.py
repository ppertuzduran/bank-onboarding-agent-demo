"""Proveedores de embeddings. Interfaz común para intercambiar local ↔ Bedrock."""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

from app.config import get_settings


class EmbeddingProvider(ABC):
    """Interfaz común. La Fase AWS implementará `BedrockTitanEmbeddingProvider`."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Devuelve un vector por texto, en el mismo orden."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...

    @property
    @abstractmethod
    def model_id(self) -> str:
        ...


class LocalEmbeddingProvider(EmbeddingProvider):
    """Usa sentence-transformers en local. Multilingüe (incluye español)."""

    def __init__(self, model_name: str) -> None:
        self._model_name: str = model_name
        self._model: Any | None = None
        self._dim: int | None = None

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
            self._dim = int(self._model.get_sentence_embedding_dimension())
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [vec.tolist() for vec in vectors]

    @property
    def dimension(self) -> int:
        if self._dim is None:
            self._load()
        assert self._dim is not None
        return self._dim

    @property
    def model_id(self) -> str:
        return self._model_name


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    return LocalEmbeddingProvider(settings.embedding_model)
