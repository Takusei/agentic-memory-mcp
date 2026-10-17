"""Tests for the storage layer (VectorStore, BM25Store, MemoryStore).

Uses temporary directories so no persistent state is left behind.
"""

from agentic_memory.schema import KeyFile, TaskMemory
from agentic_memory.store.bm25_store import BM25Store
from agentic_memory.store.memory_store import MemoryStore
from agentic_memory.store.vector_store import VectorStore

# ---------------------------------------------------------------------------
# BM25Store
# ---------------------------------------------------------------------------


class TestBM25Store:
    def _make_store(self, tmp_path):
        return BM25Store(index_path=str(tmp_path / "bm25.pkl"))

    def test_empty_search(self, tmp_path):
        store = self._make_store(tmp_path)
        results = store.search("spring boot migration")
        assert results == []

    def test_upsert_and_search(self, tmp_path):
        store = self._make_store(tmp_path)
        store.upsert(
            memory_id="mem-001",
            passages={
                "task": "Java Spring Boot migration from 2.7 to 3.2",
                "files": "pom.xml",
            },
            repo_id="payment-service",
        )
        results = store.search("spring boot migration")
        assert len(results) > 0
        assert results[0]["memory_id"] == "mem-001"

    def test_delete(self, tmp_path):
        store = self._make_store(tmp_path)
        store.upsert("mem-001", {"task": "spring boot upgrade"}, "svc")
        store.delete("mem-001")
        results = store.search("spring boot")
        assert all(r["memory_id"] != "mem-001" for r in results)

    def test_repo_filter(self, tmp_path):
        store = self._make_store(tmp_path)
        store.upsert("mem-a", {"task": "spring boot upgrade"}, "service-a")
        store.upsert("mem-b", {"task": "spring boot upgrade"}, "service-b")
        results = store.search("spring boot", repo_id="service-a")
        assert all(r["memory_id"] == "mem-a" for r in results)

    def test_persistence(self, tmp_path):
        store1 = self._make_store(tmp_path)
        store1.upsert("mem-001", {"task": "log4j upgrade"}, "svc")
        # New store instance loads from disk
        store2 = self._make_store(tmp_path)
        results = store2.search("log4j")
        assert len(results) > 0


# ---------------------------------------------------------------------------
# VectorStore
# ---------------------------------------------------------------------------


class TestVectorStore:
    def _make_store(self, tmp_path):
        return VectorStore(persist_dir=str(tmp_path / "chroma"))

    def test_empty_search(self, tmp_path):
        store = self._make_store(tmp_path)
        results = store.search("anything")
        assert results == []

    def test_upsert_and_search(self, tmp_path):
        store = self._make_store(tmp_path)
        store.upsert_passages(
            memory_id="mem-001",
            passages={"task": "Java Spring Boot migration from 2.7 to 3.2"},
            repo_id="payment-service",
        )
        results = store.search("Spring Boot upgrade")
        assert len(results) > 0
        assert results[0]["memory_id"] == "mem-001"
        assert 0.0 <= results[0]["score"] <= 1.0

    def test_delete(self, tmp_path):
        store = self._make_store(tmp_path)
        store.upsert_passages("mem-001", {"task": "spring boot upgrade"}, "svc")
        store.delete("mem-001")
        results = store.search("spring boot")
        assert all(r["memory_id"] != "mem-001" for r in results)

    def test_repo_filter(self, tmp_path):
        store = self._make_store(tmp_path)
        store.upsert_passages("mem-a", {"task": "spring boot upgrade"}, "service-a")
        store.upsert_passages("mem-b", {"task": "spring boot upgrade"}, "service-b")
        results = store.search("spring boot", repo_id="service-a")
        assert all(r["memory_id"] == "mem-a" for r in results)


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------


def _make_memory(**kwargs) -> TaskMemory:
    defaults = dict(
        repo_id="test-repo",
        task_pattern="Test pattern",
        description="A test memory.",
        key_files=[KeyFile(path="src/Main.java")],
        solution_steps=["step 1", "step 2"],
        pitfalls=["watch out for X"],
    )
    defaults.update(kwargs)
    return TaskMemory(**defaults)


class TestMemoryStore:
    def _make_store(self, tmp_path):
        return MemoryStore(data_dir=str(tmp_path))

    def test_upsert_and_get(self, tmp_path):
        store = self._make_store(tmp_path)
        m = _make_memory()
        store.upsert(m)
        retrieved = store.get(m.id)
        assert retrieved is not None
        assert retrieved.id == m.id
        assert retrieved.task_pattern == m.task_pattern
        assert retrieved.key_files[0].path == "src/Main.java"

    def test_get_missing(self, tmp_path):
        store = self._make_store(tmp_path)
        assert store.get("mem-nonexistent") is None

    def test_delete(self, tmp_path):
        store = self._make_store(tmp_path)
        m = _make_memory()
        store.upsert(m)
        store.delete(m.id)
        assert store.get(m.id) is None

    def test_update_confidence(self, tmp_path):
        store = self._make_store(tmp_path)
        m = _make_memory()
        store.upsert(m)
        store.update_confidence(m.id, delta=+0.5)
        updated = store.get(m.id)
        assert abs(updated.confidence - 1.0) < 1e-6  # clamped at 1.0

    def test_update_confidence_decay(self, tmp_path):
        store = self._make_store(tmp_path)
        m = _make_memory()
        m.confidence = 0.5
        store.upsert(m)
        store.update_confidence(m.id, delta=-0.3)
        updated = store.get(m.id)
        assert abs(updated.confidence - 0.2) < 1e-6

    def test_update_confidence_floor(self, tmp_path):
        store = self._make_store(tmp_path)
        m = _make_memory()
        m.confidence = 0.1
        store.upsert(m)
        store.update_confidence(m.id, delta=-0.5)
        updated = store.get(m.id)
        assert updated.confidence == 0.0

    def test_list_all(self, tmp_path):
        store = self._make_store(tmp_path)
        m1 = _make_memory(repo_id="repo-a")
        m2 = _make_memory(repo_id="repo-b")
        store.upsert(m1)
        store.upsert(m2)
        all_mems = store.list_all()
        assert len(all_mems) == 2

    def test_list_all_filtered(self, tmp_path):
        store = self._make_store(tmp_path)
        m1 = _make_memory(repo_id="repo-a")
        m2 = _make_memory(repo_id="repo-b")
        store.upsert(m1)
        store.upsert(m2)
        filtered = store.list_all(repo_id="repo-a")
        assert len(filtered) == 1
        assert filtered[0].id == m1.id
