"""Tests for the MCP server tools."""

from unittest.mock import MagicMock, patch

import pytest

from agentic_memory.schema import KeyFile, TaskMemory
from agentic_memory.store.memory_store import MemoryStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_memory(store: MemoryStore, **kwargs) -> TaskMemory:
    defaults = dict(
        repo_id="test-repo",
        task_pattern="Spring Boot migration",
        description="Upgrade from 2.7 to 3.2",
        key_files=[KeyFile(path="pom.xml")],
        solution_steps=["Update pom.xml", "Replace javax"],
        pitfalls=["javax→jakarta"],
        confidence=0.9,
    )
    defaults.update(kwargs)
    m = TaskMemory(**defaults)
    store.upsert(m)
    return m


# ---------------------------------------------------------------------------
# Import server functions with patched global state
# ---------------------------------------------------------------------------


def _import_server_with_store(store: MemoryStore):
    """Import mcp_server.server functions bound to a custom store."""
    import agentic_memory.mcp_server.server as srv

    retriever_mock = MagicMock()
    retriever_mock.search.return_value = []

    # Patch module-level globals so tools use our temp store
    with (
        patch.object(srv, "store", store),
        patch.object(srv, "retriever", retriever_mock),
    ):
        yield srv, retriever_mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMemoryGet:
    def test_get_existing_l2(self, tmp_path):
        store = MemoryStore(data_dir=str(tmp_path))
        m = _seed_memory(store)

        import agentic_memory.mcp_server.server as srv

        with patch.object(srv, "store", store):
            result = srv.memory_get(m.id, level="L2")
        assert result is not None
        assert result["id"] == m.id
        assert "solution_steps" in result

    def test_get_existing_l1(self, tmp_path):
        store = MemoryStore(data_dir=str(tmp_path))
        m = _seed_memory(store)
        import agentic_memory.mcp_server.server as srv

        with patch.object(srv, "store", store):
            result = srv.memory_get(m.id, level="L1")
        assert "step_count" in result
        assert "solution_steps" not in result

    def test_get_missing(self, tmp_path):
        store = MemoryStore(data_dir=str(tmp_path))
        import agentic_memory.mcp_server.server as srv

        with patch.object(srv, "store", store):
            result = srv.memory_get("mem-nonexistent")
        assert result is None


class TestMemoryRate:
    def test_rate_correct(self, tmp_path):
        store = MemoryStore(data_dir=str(tmp_path))
        m = _seed_memory(store, confidence=0.5)
        import agentic_memory.mcp_server.server as srv

        with patch.object(srv, "store", store):
            result = srv.memory_rate(m.id, factual="correct")
        assert result["ok"] is True
        assert result["new_confidence"] == pytest.approx(0.6, abs=1e-6)

    def test_rate_incorrect(self, tmp_path):
        store = MemoryStore(data_dir=str(tmp_path))
        m = _seed_memory(store, confidence=0.8)
        import agentic_memory.mcp_server.server as srv

        with patch.object(srv, "store", store):
            result = srv.memory_rate(m.id, factual="incorrect", note="file moved")
        assert result["ok"] is True
        assert result["new_confidence"] == pytest.approx(0.5, abs=1e-6)

    def test_rate_incorrect_queues_redistillation(self, tmp_path):
        """factual='incorrect' flips the source trace to needs_redistill and
        does not call the pipeline inline."""
        import agentic_memory.mcp_server.server as srv
        from agentic_memory.store.trace_status_store import (
            NEEDS_REDISTILL,
            TraceStatusStore,
        )

        store = MemoryStore(data_dir=str(tmp_path))
        trace_id = "trace-test-001"
        m = _seed_memory(store, confidence=0.8, source_trace_id=trace_id)

        status_store = TraceStatusStore(str(tmp_path / "status.db"))
        status_store.enqueue(trace_id)
        # Simulate the trace having been already processed once.
        status_store.claim_next()
        status_store.mark_processed(trace_id, memory_id=m.id)

        with (
            patch.object(srv, "store", store),
            patch.object(srv, "status_store", status_store),
        ):
            result = srv.memory_rate(m.id, factual="incorrect", note="middleware moved")

        assert result["ok"] is True
        assert result["redistill_queued"] is True
        assert result["redistill_trace_id"] == trace_id
        assert result["new_confidence"] == pytest.approx(0.5, abs=1e-6)

        row = status_store.get(trace_id)
        assert row["status"] == NEEDS_REDISTILL
        assert row["note"] == "middleware moved"
        status_store.close()

    def test_rate_incorrect_without_trace_row_logs_warning(self, tmp_path, caplog):
        """If the source trace has no status row, the call still succeeds and
        logs a warning rather than crashing."""
        import logging

        import agentic_memory.mcp_server.server as srv
        from agentic_memory.store.trace_status_store import TraceStatusStore

        store = MemoryStore(data_dir=str(tmp_path))
        m = _seed_memory(store, confidence=0.8, source_trace_id="orphan-trace")
        status_store = TraceStatusStore(str(tmp_path / "status.db"))

        with (
            patch.object(srv, "store", store),
            patch.object(srv, "status_store", status_store),
            caplog.at_level(logging.WARNING, logger="agentic_memory.mcp_server.server"),
        ):
            result = srv.memory_rate(m.id, factual="incorrect", note="stale")

        assert result["ok"] is True
        assert result["redistill_queued"] is False
        assert result["redistill_trace_id"] is None
        assert any("re-distillation" in r.message.lower() for r in caplog.records)
        status_store.close()

    def test_rate_not_found(self, tmp_path):
        store = MemoryStore(data_dir=str(tmp_path))
        import agentic_memory.mcp_server.server as srv

        with patch.object(srv, "store", store):
            result = srv.memory_rate("mem-ghost", factual="correct")
        assert result["ok"] is False
        assert "not found" in result["error"]


class TestMemoryAdd:
    def test_add_creates_memory(self, tmp_path):
        store = MemoryStore(data_dir=str(tmp_path))
        import agentic_memory.mcp_server.server as srv

        with patch.object(srv, "store", store):
            result = srv.memory_add(
                repo_id="svc",
                task_pattern="Add health endpoint",
                description="Add GET /health",
                key_files=["HealthController.java"],
                solution_steps=["Create controller"],
                pitfalls=[],
            )
        assert result["ok"] is True
        memory_id = result["memory_id"]
        m = store.get(memory_id)
        assert m is not None
        assert m.task_pattern == "Add health endpoint"


class TestMemoryUpdate:
    def test_update_description(self, tmp_path):
        store = MemoryStore(data_dir=str(tmp_path))
        m = _seed_memory(store)
        import agentic_memory.mcp_server.server as srv

        with patch.object(srv, "store", store):
            result = srv.memory_update(m.id, description="Updated description")
        assert result["ok"] is True
        updated = store.get(m.id)
        assert updated.description == "Updated description"

    def test_update_not_found(self, tmp_path):
        store = MemoryStore(data_dir=str(tmp_path))
        import agentic_memory.mcp_server.server as srv

        with patch.object(srv, "store", store):
            result = srv.memory_update("mem-ghost", description="x")
        assert result["ok"] is False


class TestMemoryDelete:
    def test_delete_existing(self, tmp_path):
        store = MemoryStore(data_dir=str(tmp_path))
        m = _seed_memory(store)
        import agentic_memory.mcp_server.server as srv

        with patch.object(srv, "store", store):
            result = srv.memory_delete(m.id)
        assert result["ok"] is True
        assert store.get(m.id) is None

    def test_delete_not_found(self, tmp_path):
        store = MemoryStore(data_dir=str(tmp_path))
        import agentic_memory.mcp_server.server as srv

        with patch.object(srv, "store", store):
            result = srv.memory_delete("mem-ghost")
        assert result["ok"] is False
        assert "not found" in result["error"]


class TestMemoryLookup:
    def test_lookup_delegates_to_retriever(self, tmp_path):
        store = MemoryStore(data_dir=str(tmp_path))
        m = _seed_memory(store)
        from agentic_memory.schema import RetrievalResult

        mock_retriever = MagicMock()
        mock_retriever.search.return_value = [RetrievalResult(memory=m, score=0.88)]

        import agentic_memory.mcp_server.server as srv

        with (
            patch.object(srv, "store", store),
            patch.object(srv, "retriever", mock_retriever),
        ):
            result = srv.memory_lookup(task="spring boot upgrade", repo_id="test-repo")

        assert len(result) == 1
        assert result[0]["id"] == m.id
        assert result[0]["score"] == pytest.approx(0.88, abs=1e-6)
        # L0 only — no solution_steps
        assert "solution_steps" not in result[0]


class TestMemorySaveTrace:
    def test_save_trace_enqueues_and_returns_pending(self, tmp_path):
        """memory_save_trace writes the file and enqueues, does not call pipeline."""
        import json

        import agentic_memory.mcp_server.server as srv
        from agentic_memory.store.trace_status_store import PENDING, TraceStatusStore

        trace_dir = tmp_path / "traces"
        status_store = TraceStatusStore(str(tmp_path / "status.db"))

        with (
            patch.object(srv, "_TRACE_DIR", str(trace_dir)),
            patch.object(srv, "status_store", status_store),
            patch.object(srv, "_get_pipeline") as mock_factory,
        ):
            result = srv.memory_save_trace(
                repo_id="svc",
                task="do a thing",
                messages=[{"role": "assistant", "content": "plan"}],
            )

        assert result["ok"] is True
        assert result["status"] == "pending"
        tid = result["trace_id"]

        # Trace file persisted
        path = trace_dir / f"{tid}.json"
        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded["task"] == "do a thing"

        # Status row created
        row = status_store.get(tid)
        assert row is not None
        assert row["status"] == PENDING

        # Pipeline must not be invoked from the tool path
        mock_factory.assert_not_called()
        status_store.close()

    def test_save_trace_stores_raw_messages_without_filtering(self, tmp_path):
        """Raw trace is persisted verbatim; memory_* filtering happens later at
        flatten_trace time, not at save time."""
        import json

        import agentic_memory.mcp_server.server as srv
        from agentic_memory.store.trace_status_store import TraceStatusStore

        trace_dir = tmp_path / "traces"
        status_store = TraceStatusStore(str(tmp_path / "status.db"))
        messages = [
            {"role": "assistant", "content": "plan"},
            {"role": "tool", "content": "memory_lookup(task='x', repo_id='svc')"},
            {"role": "result", "content": '[{"id": "mem-1"}]'},
            {"role": "tool", "content": "read_file(src/app.py)"},
            {"role": "result", "content": "file contents"},
            {"role": "final", "content": "done"},
        ]

        with (
            patch.object(srv, "_TRACE_DIR", str(trace_dir)),
            patch.object(srv, "status_store", status_store),
        ):
            result = srv.memory_save_trace(
                repo_id="svc",
                task="do a thing",
                messages=messages,
            )

        tid = result["trace_id"]
        loaded = json.loads((trace_dir / f"{tid}.json").read_text())

        # Stored exactly as provided — including the memory_* bookkeeping rows.
        assert loaded["messages"] == messages
        status_store.close()
