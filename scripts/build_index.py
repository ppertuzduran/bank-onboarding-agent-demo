"""Lee los documentos cifrados, los descifra en memoria, chunking por sección,
genera embeddings y los indexa en ChromaDB.

Los documentos solo existen en claro durante la ejecución de este script,
en memoria, nunca escritos a disco.
"""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.rag.chunker import Chunk, SectionChunker
from app.rag.embedder import get_embedding_provider
from app.rag.retriever import get_retriever
from app.security import EncryptionService


def _infer_product_from_filename(name: str) -> str:
    """Deriva el producto del nombre de archivo (p. ej. politica_cuenta_ahorros.md.enc -> cuenta_ahorros)."""
    stem = name.replace(".md.enc", "").replace(".md", "")
    if stem.startswith("politica_"):
        candidate = stem[len("politica_") :]
    else:
        candidate = stem
    if candidate == "kyc_general":
        return "general"
    return candidate


def main() -> int:
    settings = get_settings()
    enc_dir: Path = settings.docs_encrypted_dir
    service = EncryptionService.from_settings(settings)
    chunker = SectionChunker()
    embedder = get_embedding_provider()
    retriever = get_retriever()

    print("=" * 70)
    print(f"Modelo embeddings : {embedder.model_id}")
    print(f"Dimensión vector  : {embedder.dimension}")
    print(f"Colección Chroma  : {settings.chroma_collection}")
    print(f"Persist dir       : {settings.chroma_dir}")
    print("=" * 70)

    print("Reseteando coleccion Chroma...")
    retriever.reset()

    all_chunks: list[Chunk] = []
    docs_processed = 0

    for enc_path in sorted(enc_dir.glob("*.enc")):
        plain_bytes = service.decrypt(enc_path.read_bytes())
        content = plain_bytes.decode("utf-8")
        product = _infer_product_from_filename(enc_path.name)
        document_name = enc_path.name.replace(".md.enc", "")
        chunks = chunker.chunk_text(
            document=document_name,
            text=content,
            metadata={"product": product},
        )
        all_chunks.extend(chunks)
        docs_processed += 1
        print(f"  {enc_path.name} -> {len(chunks)} chunks (product={product})")

    inserted = retriever.upsert(all_chunks)
    print(f"Indexados {inserted} chunks de {docs_processed} documentos en Chroma "
          f"(dim={embedder.dimension})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
