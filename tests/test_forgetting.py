"""Tests for the forgetting subsystem (archive + ForgettingWorker)."""

from datetime import datetime, timedelta, timezone

from agentic_memory.forgetting.worker import ForgettingWorker, evaluate_memory
from agentic_memory.schema import KeyFile, TaskMemory
from agentic_memory.setting import (
    FORGET_CONFIDENCE_FLOOR,
    FORGET_DECAY_COUNT_THRESHOLD,
    FORGET_MIN_AGE_DAYS,
    FORGET_PROTECT_USE_COUNT,
    FORGET_STALENESS_DAYS,
    FORGET_UNUSED_AGE_DAYS,
)
from agentic_memory.store.memory_store import MemoryStore

NOW = datetime(2026, 6, 4, tzinfo=timezone.utc)


def _iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


def _make_memory(**kwargs) -> TaskMemory:
    defaults = dict(
        repo_id="test-repo",
        task_pattern="Test pattern",
        description="A test memory.",
        key_files=[KeyFile(path="src/Main.java")],
        solution_steps=["step 1", "step 2"],
        pitfalls=["watch out for X"],
        confidence=0.8,
        created_at=_iso(60),
        updated_at=_iso(60),
    )
    defaults.update(kwargs)
    return TaskMemory(**defaults)


# ---------------------------------------------------------------------------
# evaluate_memory
# ---------------------------------------------------------------------------


class TestEvaluateMemory:
    def test_healthy_memory_kept(self):
        m = _make_memory(confidence=0.8, use_count=2, updated_at=_iso(5))
        assert evaluate_memory(m, NOW) is None

    def test_grace_period_protects_young(self):
        # Young memory at the floor is still protected by the grace period.
        m = _make_memory(
            confidence=0.0,
            created_at=_iso(FORGET_MIN_AGE_DAYS - 1),
            updated_at=_iso(FORGET_MIN_AGE_DAYS - 1),
        )
        assert evaluate_memory(m, NOW) is None

    def test_proven_useful_protected(self):
        # High use_count + healthy confidence is protected even when stale.
        m = _make_memory(
            confidence=0.5,
            use_count=FORGET_PROTECT_USE_COUNT,
            updated_at=_iso(FORGET_STALENESS_DAYS + 10),
            last_used_at=_iso(FORGET_STALENESS_DAYS + 10),
        )
        assert evaluate_memory(m, NOW) is None

    def test_low_confidence(self):
        m = _make_memory(confidence=FORGET_CONFIDENCE_FLOOR, decay_count=0)
        assert evaluate_memory(m, NOW) == "low_confidence"

    def test_repeated_incorrect(self):
        m = _make_memory(
            confidence=FORGET_CONFIDENCE_FLOOR,
            decay_count=FORGET_DECAY_COUNT_THRESHOLD,
        )
        assert evaluate_memory(m, NOW) == "repeated_incorrect"

    def test_single_incorrect_not_forgotten(self):
        # One incorrect rating only queues re-distillation; confidence well
        # above the floor must not be archived.
        m = _make_memory(
            confidence=0.5,
            decay_count=1,
            use_count=1,
            updated_at=_iso(5),
            last_used_at=_iso(5),
        )
        assert evaluate_memory(m, NOW) is None

    def test_stale(self):
        m = _make_memory(
            confidence=0.8,
            use_count=1,
            updated_at=_iso(FORGET_STALENESS_DAYS + 1),
            last_used_at=_iso(FORGET_STALENESS_DAYS + 1),
        )
        assert evaluate_memory(m, NOW) == "stale"

    def test_last_used_at_overrides_updated_at(self):
        # Recently used but old updated_at => not stale.
        m = _make_memory(
            confidence=0.8,
            use_count=1,
            updated_at=_iso(FORGET_STALENESS_DAYS + 5),
            last_used_at=_iso(1),
        )
        assert evaluate_memory(m, NOW) is None

    def test_never_used(self):
        m = _make_memory(
            confidence=0.8,
            use_count=0,
            created_at=_iso(FORGET_UNUSED_AGE_DAYS + 1),
            updated_at=_iso(1),
            last_used_at="",
        )
        assert evaluate_memory(m, NOW) == "never_used"


# ---------------------------------------------------------------------------
# MemoryStore.archive
# ---------------------------------------------------------------------------


class TestArchive:
    def _make_store(self, tmp_path):
        return MemoryStore(data_dir=str(tmp_path))

    def test_archive_moves_and_deindexes(self, tmp_path):
        store = self._make_store(tmp_path)
        m = _make_memory()
        store.upsert(m)

        assert store.archive(m.id, "low_confidence") is True

        # Gone from live store + indexes.
        assert store.get(m.id) is None
        assert all(
            r["memory_id"] != m.id for r in store.bm25_store.search("test pattern")
        )

        # Recoverable copy exists with metadata stamped.
        archive_path = tmp_path / "archive" / f"{m.id}.json"
        assert archive_path.exists()
        import json

        data = json.loads(archive_path.read_text())
        assert data["forget_reason"] == "low_confidence"
        assert data["archived_at"]

    def test_archive_missing_returns_false(self, tmp_path):
        store = self._make_store(tmp_path)
        assert store.archive("mem-nonexistent", "stale") is False


# ---------------------------------------------------------------------------
# ForgettingWorker
# ---------------------------------------------------------------------------


class TestForgettingWorker:
    def _make_store(self, tmp_path):
        return MemoryStore(data_dir=str(tmp_path))

    def test_sweep_archives_only_candidates(self, tmp_path):
        store = self._make_store(tmp_path)
        keep = _make_memory(confidence=0.8, use_count=2, updated_at=_iso(5))
        drop = _make_memory(confidence=FORGET_CONFIDENCE_FLOOR)
        store.upsert(keep)
        store.upsert(drop)

        worker = ForgettingWorker(store=store)
        summary = worker.sweep_once(now=NOW)

        assert summary["scanned"] == 2
        assert summary["archived"] == 1
        assert summary["reasons"].get("low_confidence") == 1
        assert store.get(keep.id) is not None
        assert store.get(drop.id) is None

    def test_sweep_respects_batch_limit(self, tmp_path):
        store = self._make_store(tmp_path)
        for _ in range(3):
            store.upsert(_make_memory(confidence=FORGET_CONFIDENCE_FLOOR))

        worker = ForgettingWorker(store=store, batch_limit=1)
        summary = worker.sweep_once(now=NOW)

        assert summary["archived"] == 1
        assert len(store.list_all()) == 2

    def test_start_stop_lifecycle(self, tmp_path):
        store = self._make_store(tmp_path)
        worker = ForgettingWorker(store=store, poll_interval=60)
        worker.start()
        assert worker._thread is not None and worker._thread.is_alive()
        worker.stop(timeout=2.0)
        assert not worker._thread.is_alive()
