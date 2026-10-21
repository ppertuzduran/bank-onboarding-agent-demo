"""Cifra los documentos sintéticos y los escribe en `data/encrypted/`.

Los originales (en `data/synthetic_docs/`) deben eliminarse o excluirse de git
en un entorno real. Para esta PoC los mantenemos para facilitar la revisión
visual, pero el pipeline de indexado lee los cifrados.
"""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.security import EncryptionService


def main() -> int:
    settings = get_settings()
    service = EncryptionService.from_settings(settings)

    plain_dir: Path = settings.docs_plain_dir
    enc_dir: Path = settings.docs_encrypted_dir
    enc_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for md_path in sorted(plain_dir.glob("*.md")):
        token = service.encrypt(md_path.read_bytes())
        out_path = enc_dir / f"{md_path.name}.enc"
        out_path.write_bytes(token)
        count += 1

    print(f"Cifrados {count} documentos -> {enc_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
