"""Retriever sobre ChromaDB persistente."""

from __future__ import annotations

import contextlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.rag.chunker import Chunk
from app.rag.embedder import EmbeddingProvider, get_embedding_provider


class RetrievalHit(BaseModel):
    document: str
    section: str
    text: str
    score: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChromaRetriever:
    """Encapsula el acceso a ChromaDB. Expone upsert + query."""

    def __init__(
        self,
        persist_dir: Path,
        collection_name: str,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._persist_dir: Path = persist_dir
        self._collection_name: str = collection_name
        self._embedder: EmbeddingProvider = embedding_provider
        self._client: Any | None = None
        self._collection: Any | None = None

    def _get_collection(self) -> Any:
        if self._collection is not None:
            return self._collection
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self._persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection

    def reset(self) -> None:
        """Elimina y recrea la colección (útil para re-indexar en experimentos)."""
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        self._persist_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(
            path=str(self._persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        with contextlib.suppress(Exception):
            client.delete_collection(self._collection_name)
        self._client = client
        self._collection = client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        collection = self._get_collection()
        ids = [f"{c.document}::{c.section}::{i}" for i, c in enumerate(chunks)]
        documents = [c.display_text for c in chunks]
        metadatas = [
            {
                "document": c.document,
                "section": c.section,
                "level": c.level,
                **c.metadata,
            }
            for c in chunks
        ]
        embeddings = self._embedder.embed(documents)
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
        return len(chunks)

    def query(
        self,
        text: str,
        top_k: int = 3,
        where: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]:
        collection = self._get_collection()
        query_vec = self._embedder.embed([text])[0]
        result = collection.query(
            query_embeddings=[query_vec],
            n_results=top_k,
            where=where,
        )
        hits: list[RetrievalHit] = []
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        for doc_text, meta, dist in zip(documents, metadatas, distances, strict=False):
            score = max(0.0, min(1.0, 1.0 - float(dist)))
            hits.append(
                RetrievalHit(
                    document=str(meta.get("document", "")),
                    section=str(meta.get("section", "")),
                    text=doc_text,
                    score=score,
                    metadata=dict(meta),
                )
            )
        return hits


@lru_cache(maxsize=1)
def get_retriever() -> ChromaRetriever:
    settings = get_settings()
    return ChromaRetriever(
        persist_dir=settings.chroma_dir,
        collection_name=settings.chroma_collection,
        embedding_provider=get_embedding_provider(),
    )
