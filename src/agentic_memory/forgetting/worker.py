"""Background forgetting worker.

Periodically scans the memory store and soft-archives memories that are no
longer valuable, using several independent signals. Mirrors the lifecycle of
:class:`~agentic_memory.distillation.worker.DistillationWorker` (daemon thread,
``start()`` / ``stop()``, poll loop driven by a stop event).

Forgetting is intentionally conservative: memories are *archived* (recoverable),
never hard-deleted, and young or heavily-used memories are protected.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from agentic_memory.schema import TaskMemory
from agentic_memory.setting import (
    FORGET_BATCH_LIMIT,
    FORGET_CONFIDENCE_FLOOR,
    FORGET_DECAY_COUNT_THRESHOLD,
    FORGET_MIN_AGE_DAYS,
    FORGET_POLL_INTERVAL_SEC,
    FORGET_PROTECT_USE_COUNT,
    FORGET_STALENESS_DAYS,
    FORGET_UNUSED_AGE_DAYS,
)
from agentic_memory.store.memory_store import MemoryStore

logger = logging.getLogger(__name__)


def _parse_iso(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp into an aware datetime, or None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _age_days(timestamp: str, now: datetime) -> float | None:
    """Whole/fractional days between *timestamp* and *now*, or None if unparseable."""
    dt = _parse_iso(timestamp)
    if dt is None:
        return None
    return (now - dt).total_seconds() / 86400.0


def evaluate_memory(memory: TaskMemory, now: datetime) -> str | None:
    """Decide whether *memory* should be forgotten.

    Returns a short reason string if the memory is a forgetting candidate, or
    None to keep it. Rules are evaluated in priority order; protections win.

    Reasons:
        - "repeated_incorrect": sustained negative feedback (decay_count high AND
          confidence at/below the floor). Requires both so a single incorrect
          rating — which only queues a re-distillation — never triggers eviction.
        - "low_confidence": confidence at/below the floor from any cause.
        - "stale": no activity (last_used_at or updated_at) for too long.
        - "never_used": never rated useful and older than the unused-age window.
    """
    # --- Protections (never forget) ---------------------------------------
    created_age = _age_days(memory.created_at, now)
    if created_age is not None and created_age < FORGET_MIN_AGE_DAYS:
        return None  # within grace period

    if (
        memory.use_count >= FORGET_PROTECT_USE_COUNT
        and memory.confidence > FORGET_CONFIDENCE_FLOOR
    ):
        return None  # proven-useful, healthy memory

    # --- Decay-driven signals --------------------------------------------
    at_or_below_floor = memory.confidence <= FORGET_CONFIDENCE_FLOOR
    if at_or_below_floor and memory.decay_count >= FORGET_DECAY_COUNT_THRESHOLD:
        return "repeated_incorrect"
    if at_or_below_floor:
        return "low_confidence"

    # --- Time-driven signals ---------------------------------------------
    # Last activity: prefer real usage, fall back to last write.
    last_activity = memory.last_used_at or memory.updated_at
    activity_age = _age_days(last_activity, now)
    if activity_age is not None and activity_age >= FORGET_STALENESS_DAYS:
        return "stale"

    if (
        memory.use_count == 0
        and created_age is not None
        and created_age >= FORGET_UNUSED_AGE_DAYS
    ):
        return "never_used"

    return None


class ForgettingWorker:
    """Periodically archives stale / low-value memories in a background thread."""

    def __init__(
        self,
        store: MemoryStore,
        poll_interval: int = FORGET_POLL_INTERVAL_SEC,
        batch_limit: int = FORGET_BATCH_LIMIT,
    ) -> None:
        self._store = store
        self._poll_interval = poll_interval
        self._batch_limit = batch_limit
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_sweep: dict | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="ForgettingWorker", daemon=True
        )
        self._thread.start()
        logger.info(
            "ForgettingWorker started (poll=%ds, batch_limit=%d).",
            self._poll_interval,
            self._batch_limit,
        )

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.sweep_once()
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("ForgettingWorker sweep failed: %s", exc)
            self._stop.wait(self._poll_interval)

    # ------------------------------------------------------------------
    # Sweep
    # ------------------------------------------------------------------

    def sweep_once(self, now: datetime | None = None) -> dict:
        """Scan all memories once and archive forgetting candidates.

        Returns a summary dict: ``{"scanned", "archived", "reasons"}``.
        """
        now = now or datetime.now(timezone.utc)
        memories = self._store.list_all()

        archived = 0
        reasons: dict[str, int] = {}
        for memory in memories:
            if archived >= self._batch_limit:
                logger.info(
                    "ForgettingWorker hit batch limit (%d); deferring rest.",
                    self._batch_limit,
                )
                break
            reason = evaluate_memory(memory, now)
            if reason is None:
                continue
            if self._store.archive(memory.id, reason):
                archived += 1
                reasons[reason] = reasons.get(reason, 0) + 1

        summary = {
            "scanned": len(memories),
            "archived": archived,
            "reasons": reasons,
        }
        self._last_sweep = {**summary, "at": now.isoformat()}
        if archived:
            logger.info(
                "ForgettingWorker archived %d/%d memories: %s",
                archived,
                len(memories),
                reasons,
            )
        return summary

    @property
    def last_sweep(self) -> dict | None:
        return self._last_sweep
