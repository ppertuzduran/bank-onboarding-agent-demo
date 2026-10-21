"""Chunking por sección sobre documentos markdown.

Los documentos sintéticos del banco se escriben con encabezados `#`, `##`, `###`.
Cada chunk engloba una sección completa (título + párrafos hasta el siguiente título
del mismo nivel o superior). Esto se alinea con la guía del prompt: "englobar cada
sección del documento con título o subtítulo".
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field


_HEADER_RE: re.Pattern[str] = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class Chunk(BaseModel):
    """Unidad indexable: una sección con su título y texto.

    El `embedding_text` antepone el `document` y la `section` al cuerpo:
    así el vector captura la pertenencia estructural (contextual embedding)
    y el retrieval mejora cuando la query menciona el producto o el tema.
    """

    document: str
    section: str
    level: int = Field(ge=1, le=6)
    text: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def display_text(self) -> str:
        """Texto que se enviará al modelo de embeddings.

        Formato: `documento: <doc> | sección: <sección>\\n<texto>`.
        Mantiene la metadata estructural dentro del vector, no solo en el
        campo `metadata` de Chroma.
        """
        return f"documento: {self.document} | sección: {self.section}\n{self.text}".strip()


class SectionChunker:
    """Divide un documento markdown en chunks por sección.

    - Un chunk arranca en un header y termina justo antes del siguiente header
      del mismo nivel o superior.
    - El título del chunk es el texto del header que lo abre.
    - El texto es el contenido entre headers, con las subsecciones concatenadas.
    """

    def __init__(self, min_text_chars: int = 20) -> None:
        self._min_text_chars: int = min_text_chars

    def chunk_file(self, path: Path, metadata: dict[str, str] | None = None) -> list[Chunk]:
        content = path.read_text(encoding="utf-8")
        return self.chunk_text(document=path.stem, text=content, metadata=metadata or {})

    def chunk_text(
        self,
        document: str,
        text: str,
        metadata: dict[str, str] | None = None,
    ) -> list[Chunk]:
        metadata = metadata or {}
        sections = self._split_sections(text)
        chunks: list[Chunk] = []
        for section_title, level, body in sections:
            body_clean = body.strip()
            if len(body_clean) < self._min_text_chars:
                continue
            chunks.append(
                Chunk(
                    document=document,
                    section=section_title,
                    level=level,
                    text=body_clean,
                    metadata=metadata,
                )
            )
        return chunks

    @staticmethod
    def _split_sections(text: str) -> list[tuple[str, int, str]]:
        lines = text.splitlines()
        sections: list[tuple[str, int, list[str]]] = []
        current_title: str | None = None
        current_level: int = 0
        buffer: list[str] = []

        for line in lines:
            match = _HEADER_RE.match(line)
            if match:
                if current_title is not None:
                    sections.append((current_title, current_level, buffer))
                current_level = len(match.group(1))
                current_title = match.group(2).strip()
                buffer = []
            else:
                if current_title is not None:
                    buffer.append(line)

        if current_title is not None:
            sections.append((current_title, current_level, buffer))

        return [(title, level, "\n".join(body)) for title, level, body in sections]
