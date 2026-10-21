import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def pytest_configure(config) -> None:
    tmp_dir = _ROOT / "data" / "test_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DATA_DIR", str(tmp_dir))
    os.environ.setdefault("STATE_DB_PATH", str(tmp_dir / "state_test.sqlite"))
    os.environ.setdefault("CHROMA_DIR", str(tmp_dir / "chroma_test"))
    # Generamos la clave Fernet en runtime para no hardcodear secretos ni en tests.
    os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode("utf-8"))
