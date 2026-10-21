from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.schemas import AgentOutput, OnboardingRequest, Status


class SessionState(BaseModel):
    """Estado conversacional de una sesión de onboarding."""

    session_id: str
    created_at: str
    updated_at: str
    status: Status = Status.IN_PROGRESS
    payload: OnboardingRequest
    steps: list[AgentOutput] = Field(default_factory=list)
    scratch: dict[str, Any] = Field(default_factory=dict)


class SessionStore:
    """Gestiona el estado de sesiones en memoria con snapshot en SQLite.

    - `_memory` es la fuente de verdad durante el request.
    - SQLite actúa como auditoría/persistencia (una fila por session_id).
    - Thread-safe: todas las mutaciones se serializan con `_lock`.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path: Path = db_path
        self._memory: dict[str, SessionState] = {}
        self._lock: threading.Lock = threading.Lock()
        self._bootstrap_schema()

    def _bootstrap_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status     TEXT NOT NULL,
                    snapshot   TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()

    def create(self, payload: OnboardingRequest) -> SessionState:
        session_id = str(uuid.uuid4())
        now = self._now_iso()
        state = SessionState(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            payload=payload,
        )
        with self._lock:
            self._memory[session_id] = state
        self._persist(state)
        return state

    def get(self, session_id: str) -> SessionState | None:
        with self._lock:
            return self._memory.get(session_id)

    def set_status(self, session_id: str, status: Status) -> SessionState:
        with self._lock:
            state = self._memory[session_id]
            state.status = status
            state.updated_at = self._now_iso()
            snapshot = state.model_copy(deep=True)
        self._persist(snapshot)
        return snapshot

    def append_step(self, session_id: str, trace: AgentOutput) -> SessionState:
        with self._lock:
            state = self._memory[session_id]
            state.steps.append(trace)
            state.updated_at = self._now_iso()
            snapshot = state.model_copy(deep=True)
        self._persist(snapshot)
        return snapshot

    def put_scratch(self, session_id: str, key: str, value: Any) -> None:
        with self._lock:
            state = self._memory[session_id]
            state.scratch[key] = value
            state.updated_at = self._now_iso()
            snapshot = state.model_copy(deep=True)
        self._persist(snapshot)

    def _persist(self, state: SessionState) -> None:
        snapshot_json: str = state.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, created_at, updated_at, status, snapshot)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    status     = excluded.status,
                    snapshot   = excluded.snapshot
                """,
                (
                    state.session_id,
                    state.created_at,
                    state.updated_at,
                    state.status.value,
                    snapshot_json,
                ),
            )


_store_singleton: SessionStore | None = None
_store_lock = threading.Lock()


def get_session_store() -> SessionStore:
    global _store_singleton
    with _store_lock:
        if _store_singleton is None:
            _store_singleton = SessionStore(get_settings().state_db_path)
        return _store_singleton
