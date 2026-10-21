from app.rag.chunker import SectionChunker


_SAMPLE = """# Documento de prueba

## Sección A
Primer párrafo de la sección A con suficiente longitud.

## Sección B
Segunda sección con otro párrafo descriptivo.

### Subsección B.1
Contenido de la subsección anidada.

## Sección C
Última sección.
"""


def test_chunker_produces_section_per_header() -> None:
    chunker = SectionChunker()
    chunks = chunker.chunk_text(document="prueba", text=_SAMPLE, metadata={"product": "test"})
    titles = [c.section for c in chunks]
    # Nota: el top-level title (nivel 1) contiene solo texto si lo hay; en este sample
    # no tiene cuerpo propio así que se filtra por longitud mínima.
    assert "Sección A" in titles
    assert "Sección B" in titles
    assert "Subsección B.1" in titles
    assert "Sección C" in titles
    for chunk in chunks:
        assert chunk.metadata.get("product") == "test"
        assert len(chunk.text) >= 20
