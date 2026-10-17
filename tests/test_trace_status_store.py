"""Tests for the SQLite-backed trace lifecycle store."""

import threading

import pytest

from agentic_memory.store.trace_status_store import (
    FAILED,
    NEEDS_REDISTILL,
    PENDING,
    PROCESSED,
    PROCESSING,
    TraceStatusStore,
)


@pytest.fixture()
def status_store(tmp_path):
    s = TraceStatusStore(str(tmp_path / "status.db"))
    yield s
    s.close()


def test_enqueue_is_idempotent(status_store):
    status_store.enqueue("t1")
    status_store.enqueue("t1")  # OR IGNORE
    rows = status_store.list_by_status(PENDING)
    assert len(rows) == 1


def test_claim_next_returns_pending_and_advances_state(status_store):
    status_store.enqueue("t1")
    row = status_store.claim_next()
    assert row is not None
    assert row["trace_id"] == "t1"
    assert row["status"] == PROCESSING
    assert row["attempts"] == 1

    # Nothing else pending
    assert status_store.claim_next() is None


def test_claim_next_is_atomic_under_threads(status_store):
    for i in range(20):
        status_store.enqueue(f"t{i}")

    claimed: list[str] = []
    lock = threading.Lock()

    def worker():
        while True:
            row = status_store.claim_next()
            if row is None:
                return
            with lock:
                claimed.append(row["trace_id"])

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Each trace claimed exactly once
    assert sorted(claimed) == sorted(f"t{i}" for i in range(20))


def test_mark_processed_and_failed(status_store):
    status_store.enqueue("t1")
    status_store.claim_next()
    status_store.mark_processed("t1", memory_id="mem-x")
    row = status_store.get("t1")
    assert row["status"] == PROCESSED
    assert row["memory_id"] == "mem-x"

    status_store.enqueue("t2")
    status_store.claim_next()
    status_store.mark_failed("t2", error="boom")
    row = status_store.get("t2")
    assert row["status"] == FAILED
    assert "boom" in row["last_error"]


def test_mark_needs_redistill_requires_existing_row(status_store):
    # No row yet → returns False
    assert status_store.mark_needs_redistill("missing", "note") is False

    status_store.enqueue("t1")
    status_store.claim_next()
    status_store.mark_processed("t1", memory_id="mem-y")
    assert status_store.mark_needs_redistill("t1", "stale step") is True
    row = status_store.get("t1")
    assert row["status"] == NEEDS_REDISTILL
    assert row["note"] == "stale step"


def test_requeue_orphans_resets_processing(status_store):
    status_store.enqueue("t1")
    status_store.claim_next()  # PROCESSING
    status_store.enqueue("t2")
    status_store.claim_next()
    status_store.mark_processed("t2", memory_id="m")
    status_store.mark_needs_redistill("t2", "n")  # NEEDS_REDISTILL

    n = status_store.requeue_orphans()
    # Only the orphaned PROCESSING row (t1) should be reset
    assert n == 1
    assert status_store.get("t1")["status"] == PENDING
    assert status_store.get("t2")["status"] == NEEDS_REDISTILL


def test_attempts_increment_on_reclaim(status_store):
    status_store.enqueue("t1")
    row1 = status_store.claim_next()
    assert row1["attempts"] == 1
    status_store.requeue_orphans()
    row2 = status_store.claim_next()
    assert row2["attempts"] == 2
