import os
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def pytest_configure(config) -> None:
    tmp_dir = _ROOT / "data" / "test_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DATA_DIR", str(tmp_dir))
    os.environ.setdefault("STATE_DB_PATH", str(tmp_dir / "state_test.sqlite"))
    os.environ.setdefault("CHROMA_DIR", str(tmp_dir / "chroma_test"))
    # Clave Fernet determinista para tests (válida: 32 bytes urlsafe-base64).
    os.environ.setdefault("FERNET_KEY", "zmWkqD9U87KZc0Hw4JkA8xq2VvY9HdLWBwQ6uI8rN1A=")
