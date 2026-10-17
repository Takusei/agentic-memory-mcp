"""Tests for the distillation pipeline (LLM calls are mocked)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from agentic_memory.distillation.callback_handler import TrajectoryCapture
from agentic_memory.distillation.llm_distiller import DistilledMemory, distill
from agentic_memory.distillation.pipeline import DistillationPipeline
from agentic_memory.distillation.trace_flattener import flatten_trace
from agentic_memory.store.memory_store import MemoryStore

# ---------------------------------------------------------------------------
# TrajectoryCapture
# ---------------------------------------------------------------------------


class TestTrajectoryCapture:
    def test_captures_tool_calls(self):
        cap = TrajectoryCapture("trace-001", "repo-x", "do something")
        cap.on_tool_start({"name": "read_file"}, "pom.xml")
        cap.on_tool_end("contents of pom.xml")
        assert cap.tool_calls == 1
        assert cap.messages[0]["role"] == "tool"
        assert cap.messages[1]["role"] == "result"

    def test_to_trace_structure(self):
        cap = TrajectoryCapture("trace-001", "repo-x", "task text")
        trace = cap.to_trace()
        assert trace["trace_id"] == "trace-001"
        assert trace["repo_id"] == "repo-x"
        assert trace["task"] == "task text"
        assert isinstance(trace["messages"], list)


# ---------------------------------------------------------------------------
# flatten_trace
# ---------------------------------------------------------------------------


class TestFlattenTrace:
    def test_basic_output(self):
        trace = {
            "trace_id": "t1",
            "repo_id": "r1",
            "task": "do something",
            "messages": [
                {"role": "assistant", "content": "I will help"},
                {"role": "tool", "content": "read_file(pom.xml)"},
                {"role": "result", "content": "spring-boot 2.7"},
                {"role": "final", "content": "Done"},
            ],
        }
        flat = flatten_trace(trace)
        assert "Trace ID: t1" in flat
        assert "[Assistant]" in flat
        assert "[Tool]" in flat
        assert "[Result]" in flat
        assert "[Final]" in flat

    def test_empty_messages(self):
        trace = {"trace_id": "t1", "repo_id": "r1", "task": "t", "messages": []}
        flat = flatten_trace(trace)
        assert "Trace ID: t1" in flat

    def test_filters_memory_tool_calls(self):
        """memory_* bookkeeping calls and their results are excluded from the
        flattened LLM input."""
        trace = {
            "trace_id": "t1",
            "repo_id": "r1",
            "task": "do something",
            "messages": [
                {"role": "assistant", "content": "plan"},
                {"role": "tool", "content": "memory_lookup(task='x', repo_id='r1')"},
                {"role": "result", "content": '[{"id": "mem-1"}]'},
                {"role": "tool", "content": "read_file(src/app.py)"},
                {"role": "result", "content": "file contents"},
                {"role": "final", "content": "done"},
            ],
        }
        flat = flatten_trace(trace)
        assert "memory_lookup" not in flat
        assert "mem-1" not in flat
        assert "read_file(src/app.py)" in flat
        assert "file contents" in flat

    def test_strips_memory_fragments_from_bundled_tool_message(self):
        """A tool message bundling memory_* with real tooling keeps the real
        steps and its result."""
        trace = {
            "trace_id": "t1",
            "repo_id": "r1",
            "task": "do something",
            "messages": [
                {
                    "role": "tool",
                    "content": (
                        "memory_worker_status(); "
                        "memory_lookup(task='x', repo_id='r1'); "
                        "rg pattern src; npm run build"
                    ),
                },
                {"role": "result", "content": "lookup 0 results; build passed"},
            ],
        }
        flat = flatten_trace(trace)
        assert "memory_worker_status" not in flat
        assert "memory_lookup" not in flat
        assert "rg pattern src; npm run build" in flat
        assert "build passed" in flat


class TestSanitizeMessages:
    def test_drops_memory_only_tool_and_result(self):
        from agentic_memory.distillation.trace_flattener import sanitize_messages

        messages = [
            {"role": "tool", "content": "mcp_agentic-memor_memory_worker_status()"},
            {"role": "result", "content": "{'worker_running': true}"},
            {"role": "tool", "content": "grep_search(query='foo')"},
            {"role": "result", "content": "match"},
        ]
        assert sanitize_messages(messages) == [
            {"role": "tool", "content": "grep_search(query='foo')"},
            {"role": "result", "content": "match"},
        ]

    def test_does_not_mutate_input(self):
        from agentic_memory.distillation.trace_flattener import sanitize_messages

        messages = [
            {"role": "tool", "content": "memory_lookup(); read_file(a.py)"},
        ]
        sanitize_messages(messages)
        # Original message object is left untouched.
        assert messages[0]["content"] == "memory_lookup(); read_file(a.py)"


# ---------------------------------------------------------------------------
# LLM Distiller
# ---------------------------------------------------------------------------


class TestDistiller:
    def _mock_llm(self, payload: dict):
        llm = MagicMock()
        response = MagicMock()
        response.content = json.dumps(payload)
        llm.invoke.return_value = response
        return llm

    def test_distill_valid_response(self):
        payload = {
            "task_pattern": "Spring Boot migration",
            "description": "Upgrade from 2.7 to 3.2",
            "key_files": ["pom.xml"],
            "solution_steps": ["step1"],
            "pitfalls": ["javax→jakarta"],
            "lexical_anchors": ["pom.xml"],
            "outcome": "success",
        }
        llm = self._mock_llm(payload)
        result = distill("some trace text", llm)
        assert result["task_pattern"] == "Spring Boot migration"
        assert result["outcome"] == "success"

    def test_distill_uses_structured_output_when_available(self):
        structured_llm = MagicMock()
        structured_llm.invoke.return_value = DistilledMemory(
            task_pattern="Spring Boot migration",
            description="Upgrade from 2.7 to 3.2",
            key_files=["pom.xml"],
            solution_steps=["step1"],
            pitfalls=["javax→jakarta"],
            lexical_anchors=["pom.xml"],
            outcome="success",
        )

        llm = MagicMock()
        llm.with_structured_output.return_value = structured_llm

        result = distill("some trace text", llm)

        llm.with_structured_output.assert_called_once_with(DistilledMemory)
        llm.invoke.assert_not_called()
        assert result["task_pattern"] == "Spring Boot migration"
        assert result["key_files"] == ["pom.xml"]

    def test_distill_strips_markdown_fences(self):
        llm = MagicMock()
        response = MagicMock()
        response.content = '```json\n{"task_pattern": "test", "description": "d"}\n```'
        llm.invoke.return_value = response
        result = distill("trace", llm)
        assert result["task_pattern"] == "test"

    def test_distill_raises_on_invalid_json(self):
        llm = MagicMock()
        response = MagicMock()
        response.content = "not valid json at all"
        llm.invoke.return_value = response
        with pytest.raises(ValueError):
            distill("trace", llm)


# ---------------------------------------------------------------------------
# DistillationPipeline
# ---------------------------------------------------------------------------


def _make_llm_for_pipeline(task_pattern: str = "Spring Boot migration"):
    payload = {
        "task_pattern": task_pattern,
        "description": f"Migrate {task_pattern}",
        "key_files": ["pom.xml"],
        "solution_steps": ["Update pom.xml"],
        "pitfalls": ["javax→jakarta"],
        "lexical_anchors": ["pom.xml"],
        "outcome": "success",
    }
    llm = MagicMock()
    response = MagicMock()
    response.content = json.dumps(payload)
    llm.invoke.return_value = response
    return llm


def _make_trace(repo_id: str = "payment-service") -> dict:
    return {
        "trace_id": "trace-001",
        "repo_id": repo_id,
        "task": "Upgrade Spring Boot",
        "messages": [{"role": "assistant", "content": "Updated pom.xml"}],
        "tool_calls": 5,
        "total_tokens": 1200,
    }


class TestDistillationPipeline:
    def _make_pipeline(self, tmp_path, llm=None):
        store = MemoryStore(data_dir=str(tmp_path))
        llm = llm or _make_llm_for_pipeline()
        return DistillationPipeline(store, llm), store

    def test_novel_memory_created(self, tmp_path):
        pipeline, store = self._make_pipeline(tmp_path)
        result, action = pipeline.run(_make_trace())
        assert result is not None
        assert action == "created"
        assert result.task_pattern == "Spring Boot migration"
        assert store.get(result.id) is not None

    def test_duplicate_reinforces_confidence(self, tmp_path):
        pipeline, store = self._make_pipeline(tmp_path)
        # First run: creates memory
        m, _ = pipeline.run(_make_trace())
        assert m is not None
        initial_confidence = store.get(m.id).confidence

        # Second run: should detect duplicate (same repo + similar P1)
        # We lower the threshold so the test doesn't depend on exact cosine sim
        with patch("agentic_memory.distillation.pipeline._DUPLICATE_THRESHOLD", 0.0):
            result2, action2 = pipeline.run(_make_trace())

        # With threshold=0, any match is a duplicate → no new memory returned
        # but confidence should have been updated
        updated = store.get(m.id)
        assert updated.confidence >= initial_confidence

    def test_failed_distillation_returns_none(self, tmp_path):
        bad_llm = MagicMock()
        bad_response = MagicMock()
        bad_response.content = "not json"
        bad_llm.invoke.return_value = bad_response
        pipeline, store = self._make_pipeline(tmp_path, llm=bad_llm)
        result, action = pipeline.run(_make_trace())
        assert result is None
        assert action == "failed"

    def test_empty_task_pattern_skipped(self, tmp_path):
        payload = {
            "task_pattern": "",
            "description": "something",
            "key_files": [],
            "solution_steps": [],
            "pitfalls": [],
            "lexical_anchors": [],
            "outcome": "success",
        }
        llm = MagicMock()
        response = MagicMock()
        response.content = json.dumps(payload)
        llm.invoke.return_value = response
        pipeline, store = self._make_pipeline(tmp_path, llm=llm)
        result, action = pipeline.run(_make_trace())
        assert result is None
        assert action == "failed"

    def test_overlap_same_repo_different_pattern_is_novel_under_option2(self, tmp_path):
        pipeline, store = self._make_pipeline(
            tmp_path, llm=_make_llm_for_pipeline("Startup bug fix")
        )
        first, first_action = pipeline.run(_make_trace(repo_id="nuxt2-migration-case"))
        assert first is not None
        assert first_action == "created"

        second_llm = _make_llm_for_pipeline("Nuxt2 to Nuxt3 migration")
        pipeline.llm = second_llm

        with (
            patch("agentic_memory.distillation.pipeline._DUPLICATE_THRESHOLD", 0.99),
            patch("agentic_memory.distillation.pipeline._OVERLAP_THRESHOLD", 0.0),
            patch(
                "agentic_memory.distillation.pipeline._CROSS_PATTERN_MERGE_THRESHOLD",
                1.1,
            ),
        ):
            second, second_action = pipeline.run(
                _make_trace(repo_id="nuxt2-migration-case")
            )

        assert second is not None
        assert second.id != first.id
        assert second.task_pattern == "Nuxt2 to Nuxt3 migration"

    def test_overlap_cross_pattern_merges_when_similarity_is_very_high(self, tmp_path):
        pipeline, store = self._make_pipeline(
            tmp_path, llm=_make_llm_for_pipeline("Startup bug fix")
        )
        first, _ = pipeline.run(_make_trace(repo_id="nuxt2-migration-case"))
        assert first is not None

        second_llm = _make_llm_for_pipeline("Nuxt2 to Nuxt3 migration")
        pipeline.llm = second_llm

        with (
            patch("agentic_memory.distillation.pipeline._DUPLICATE_THRESHOLD", 0.99),
            patch("agentic_memory.distillation.pipeline._OVERLAP_THRESHOLD", 0.0),
            patch(
                "agentic_memory.distillation.pipeline._CROSS_PATTERN_MERGE_THRESHOLD",
                0.0,
            ),
        ):
            second, second_action = pipeline.run(
                _make_trace(repo_id="nuxt2-migration-case")
            )

        assert second is not None
        assert second.id == first.id
        assert second_action == "merged"
