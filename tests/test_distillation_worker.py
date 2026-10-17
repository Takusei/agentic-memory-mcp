"""Tests for the DistillationWorker (no MCP, no real LLM)."""

import json
from unittest.mock import MagicMock

import pytest

from agentic_memory.distillation.worker import DistillationWorker
from agentic_memory.schema import KeyFile, TaskMemory
from agentic_memory.store.memory_store import MemoryStore
from agentic_memory.store.trace_status_store import (
    FAILED,
    PROCESSED,
    TraceStatusStore,
)


def _make_trace_file(trace_dir, trace_id: str, repo_id: str = "svc") -> dict:
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace = {
        "trace_id": trace_id,
        "repo_id": repo_id,
        "task": "do a thing",
        "messages": [{"role": "assistant", "content": "plan"}],
    }
    (trace_dir / f"{trace_id}.json").write_text(json.dumps(trace))
    return trace


def _new_memory(repo_id: str = "svc", **overrides) -> TaskMemory:
    defaults = dict(
        repo_id=repo_id,
        task_pattern="Do a thing",
        description="Does the thing",
        key_files=[KeyFile(path="x.py")],
        solution_steps=["step a"],
        pitfalls=[],
        confidence=0.8,
    )
    defaults.update(overrides)
    return TaskMemory(**defaults)


@pytest.fixture()
def worker_env(tmp_path):
    store = MemoryStore(data_dir=str(tmp_path / "mem"))
    status = TraceStatusStore(str(tmp_path / "status.db"))
    retriever = MagicMock()
    retriever.search.return_value = []
    trace_dir = tmp_path / "traces"
    yield store, status, retriever, trace_dir
    status.close()


def test_process_one_pending_marks_processed(worker_env):
    store, status, retriever, trace_dir = worker_env
    _make_trace_file(trace_dir, "t1")

    distilled = _new_memory()
    store.upsert(distilled)
    pipeline = MagicMock()
    pipeline.run.return_value = (distilled, "created")

    worker = DistillationWorker(
        store, retriever, status, str(trace_dir), pipeline_factory=lambda: pipeline
    )

    status.enqueue("t1")
    row = status.claim_next()
    result_id = worker.process_one(row)

    assert result_id == distilled.id
    final = status.get("t1")
    assert final["status"] == PROCESSED
    assert final["memory_id"] == distilled.id


def test_process_one_needs_redistill_appends_note(worker_env):
    store, status, retriever, trace_dir = worker_env
    _make_trace_file(trace_dir, "t1")

    distilled = _new_memory()
    store.upsert(distilled)
    pipeline = MagicMock()
    pipeline.run.return_value = (distilled, "created")

    worker = DistillationWorker(
        store, retriever, status, str(trace_dir), pipeline_factory=lambda: pipeline
    )

    status.enqueue("t1")
    status.claim_next()
    status.mark_processed("t1", memory_id=distilled.id)
    status.mark_needs_redistill("t1", "endpoint changed")

    row = status.claim_next()
    assert row["note"] == "endpoint changed"
    worker.process_one(row)

    pipeline.run.assert_called_once()
    called_trace = pipeline.run.call_args[0][0]
    assert any("endpoint changed" in m["content"] for m in called_trace["messages"])


def test_process_one_no_pipeline_marks_failed(worker_env):
    store, status, retriever, trace_dir = worker_env
    _make_trace_file(trace_dir, "t1")

    worker = DistillationWorker(
        store, retriever, status, str(trace_dir), pipeline_factory=lambda: None
    )
    status.enqueue("t1")
    row = status.claim_next()
    worker.process_one(row)

    assert status.get("t1")["status"] == FAILED
    assert "pipeline unavailable" in status.get("t1")["last_error"]


def test_process_one_missing_trace_file_marks_failed(worker_env):
    store, status, retriever, trace_dir = worker_env
    trace_dir.mkdir(parents=True, exist_ok=True)

    pipeline = MagicMock()
    worker = DistillationWorker(
        store, retriever, status, str(trace_dir), pipeline_factory=lambda: pipeline
    )
    status.enqueue("ghost")
    row = status.claim_next()
    worker.process_one(row)

    assert status.get("ghost")["status"] == FAILED
    pipeline.run.assert_not_called()


def test_process_one_exceeded_attempts_marks_failed(worker_env):
    store, status, retriever, trace_dir = worker_env
    _make_trace_file(trace_dir, "t1")

    pipeline = MagicMock()
    worker = DistillationWorker(
        store,
        retriever,
        status,
        str(trace_dir),
        pipeline_factory=lambda: pipeline,
        max_attempts=2,
    )

    status.enqueue("t1")
    # Exhaust attempts by simulating repeated requeue cycles
    for _ in range(3):
        row = status.claim_next()
        if row is None:
            break
        status.requeue_orphans()

    # Now manually claim once more so attempts > max
    row = status.claim_next()
    worker.process_one(row)

    assert status.get("t1")["status"] == FAILED
    assert "max_attempts" in status.get("t1")["last_error"]
    pipeline.run.assert_not_called()


def test_process_one_pipeline_returns_none_marks_processed(worker_env):
    store, status, retriever, trace_dir = worker_env
    _make_trace_file(trace_dir, "t1")

    pipeline = MagicMock()
    pipeline.run.return_value = (None, "duplicate")  # dedup / parse failure

    worker = DistillationWorker(
        store, retriever, status, str(trace_dir), pipeline_factory=lambda: pipeline
    )
    status.enqueue("t1")
    row = status.claim_next()
    result = worker.process_one(row)

    assert result is None
    assert status.get("t1")["status"] == PROCESSED
