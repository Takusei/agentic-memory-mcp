"""SQLite-backed status tracking for trace distillation.

Each trace stored on disk has exactly one row here recording where it sits in
the distillation lifecycle so the background worker can pick up new work
without re-processing history.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Status values
PENDING = "pending"
PROCESSING = "processing"
PROCESSED = "processed"
NEEDS_REDISTILL = "needs_redistill"
FAILED = "failed"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id       TEXT PRIMARY KEY,
    status         TEXT NOT NULL,
    note           TEXT,
    memory_id      TEXT,
    distill_action TEXT DEFAULT 'unknown',
    attempts       INTEGER NOT NULL DEFAULT 0,
    last_error     TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TraceStatusStore:
    """Thread-safe SQLite wrapper for trace distillation status."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            db_path, check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            # Migrate existing DBs that pre-date the distill_action column.
            try:
                self._conn.execute(
                    "ALTER TABLE traces ADD COLUMN distill_action TEXT DEFAULT 'unknown'"
                )
            except Exception:  # noqa: BLE001 - column already exists
                pass

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def enqueue(self, trace_id: str, status: str = PENDING) -> None:
        """Insert a new trace row. No-op if already present."""
        now = _now()
        with self._lock:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO traces
                  (trace_id, status, attempts, created_at, updated_at)
                VALUES (?, ?, 0, ?, ?)
                """,
                (trace_id, status, now, now),
            )

    def mark_needs_redistill(self, trace_id: str, note: str | None = None) -> bool:
        """Flip a trace to NEEDS_REDISTILL. Returns True if the row exists."""
        now = _now()
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE traces
                   SET status = ?, note = ?, updated_at = ?
                 WHERE trace_id = ?
                """,
                (NEEDS_REDISTILL, note, now, trace_id),
            )
            return cur.rowcount > 0

    def claim_next(self) -> sqlite3.Row | None:
        """Atomically move one pending/needs_redistill row into PROCESSING.

        Returns the claimed row, or None if the queue is empty.
        """
        now = _now()
        with self._lock:
            # Atomic claim via UPDATE ... RETURNING (SQLite 3.35+).
            cur = self._conn.execute(
                """
                UPDATE traces
                   SET status = ?, attempts = attempts + 1, updated_at = ?
                 WHERE trace_id = (
                     SELECT trace_id FROM traces
                      WHERE status IN (?, ?)
                      ORDER BY updated_at
                      LIMIT 1
                 )
                RETURNING *
                """,
                (PROCESSING, now, PENDING, NEEDS_REDISTILL),
            )
            row = cur.fetchone()
            return row

    def mark_processed(
        self,
        trace_id: str,
        memory_id: str | None = None,
        action: str = "unknown",
    ) -> None:
        now = _now()
        with self._lock:
            self._conn.execute(
                """
                UPDATE traces
                   SET status = ?, memory_id = ?, distill_action = ?,
                       last_error = NULL, note = NULL, updated_at = ?
                 WHERE trace_id = ?
                """,
                (PROCESSED, memory_id, action, now, trace_id),
            )

    def mark_failed(self, trace_id: str, error: str) -> None:
        now = _now()
        with self._lock:
            self._conn.execute(
                """
                UPDATE traces
                   SET status = ?, last_error = ?, updated_at = ?
                 WHERE trace_id = ?
                """,
                (FAILED, error[:1000], now, trace_id),
            )

    def requeue_orphans(self) -> int:
        """Reset rows stuck in PROCESSING (e.g. from a crash) back to PENDING.

        Returns the number of rows requeued.
        """
        now = _now()
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE traces
                   SET status = CASE
                       WHEN note IS NOT NULL THEN ?
                       ELSE ?
                   END,
                   updated_at = ?
                 WHERE status = ?
                """,
                (NEEDS_REDISTILL, PENDING, now, PROCESSING),
            )
            return cur.rowcount

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(self, trace_id: str) -> sqlite3.Row | None:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM traces WHERE trace_id = ?", (trace_id,)
            )
            return cur.fetchone()

    def list_by_status(self, status: str) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM traces WHERE status = ? ORDER BY updated_at",
                (status,),
            )
            return cur.fetchall()

    def counts(self) -> dict[str, int]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT status, COUNT(*) FROM traces GROUP BY status"
            )
            return {row[0]: row[1] for row in cur.fetchall()}

    def close(self) -> None:
        with self._lock:
            self._conn.close()
