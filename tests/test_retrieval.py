"""Tests for the retrieval pipeline."""

from unittest.mock import MagicMock

from agentic_memory.retrieval.hybrid_retriever import HybridRetriever, rrf_fusion
from agentic_memory.retrieval.progressive import format_at_level
from agentic_memory.retrieval.reranker import Reranker
from agentic_memory.schema import KeyFile, TaskMemory
from agentic_memory.store.memory_store import MemoryStore

# ---------------------------------------------------------------------------
# RRF fusion
# ---------------------------------------------------------------------------

class TestRRFFusion:
    def test_basic_fusion(self):
        bm25 = [{"memory_id": "a", "bm25_score": 1.0}, {"memory_id": "b", "bm25_score": 0.5}]
        vec  = [{"memory_id": "b", "score": 0.9},       {"memory_id": "a", "score": 0.8}]
        fused = rrf_fusion(bm25, vec)
        assert len(fused) == 2
        ids = [r["memory_id"] for r in fused]
        # Both "a" and "b" appear in both lists — "a" leads in BM25, "b" leads in vector
        assert set(ids) == {"a", "b"}

    def test_deduplication(self):
        bm25 = [{"memory_id": "x"}, {"memory_id": "x"}]
        vec  = [{"memory_id": "x"}]
        fused = rrf_fusion(bm25, vec)
        # "x" should appear only once
        assert len(fused) == 1

    def test_empty_inputs(self):
        assert rrf_fusion([], []) == []

    def test_scores_positive(self):
        bm25 = [{"memory_id": "a"}]
        vec  = [{"memory_id": "b"}]
        fused = rrf_fusion(bm25, vec)
        for r in fused:
            assert r["rrf_score"] > 0


# ---------------------------------------------------------------------------
# Progressive disclosure
# ---------------------------------------------------------------------------

class TestProgressiveDisclosure:
    def _make_memory(self):
        return TaskMemory(
            repo_id="test-repo",
            task_pattern="Spring Boot migration",
            description="Migrate from 2.7 to 3.2",
            key_files=[KeyFile(path="pom.xml")],
            solution_steps=["step1", "step2"],
            pitfalls=["pitfall1"],
            confidence=0.9,
        )

    def test_l0_fields(self):
        m = self._make_memory()
        d = format_at_level(m, score=0.85, level="L0")
        assert set(d.keys()) == {"id", "task_pattern", "description", "confidence", "score"}
        assert d["score"] == 0.85

    def test_l1_fields(self):
        m = self._make_memory()
        d = format_at_level(m, score=0.85, level="L1")
        assert "key_files" in d
        assert "step_count" in d
        assert d["step_count"] == 2
        assert d["pitfall_count"] == 1

    def test_l2_fields(self):
        m = self._make_memory()
        d = format_at_level(m, score=0.85, level="L2")
        assert "solution_steps" in d
        assert "pitfalls" in d
        assert len(d["solution_steps"]) == 2


# ---------------------------------------------------------------------------
# Reranker (mocked model)
# ---------------------------------------------------------------------------

class TestReranker:
    def test_rerank_returns_top_k(self):
        reranker = Reranker()
        # Mock the underlying model
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.3, 0.7]
        reranker._model = mock_model

        candidates = [
            {"memory_id": "a", "description": "Spring Boot migration"},
            {"memory_id": "b", "description": "Log4j upgrade"},
            {"memory_id": "c", "description": "Add endpoint"},
        ]
        results = reranker.rerank("spring boot upgrade", candidates, top_k=2)
        assert len(results) == 2
        assert results[0]["memory_id"] == "a"  # highest score 0.9
        assert results[1]["memory_id"] == "c"  # second highest 0.7

    def test_rerank_empty_candidates(self):
        reranker = Reranker()
        assert reranker.rerank("query", [], top_k=5) == []


# ---------------------------------------------------------------------------
# HybridRetriever integration (with real stores in tmpdir)
# ---------------------------------------------------------------------------

class TestHybridRetriever:
    def _make_retriever(self, tmp_path):
        store = MemoryStore(data_dir=str(tmp_path))
        # Use a mock reranker to avoid downloading models in CI
        mock_reranker = MagicMock(spec=Reranker)

        def fake_rerank(query, candidates, top_k=5):
            for i, c in enumerate(candidates):
                c["rerank_score"] = 1.0 - i * 0.1
            return candidates[:top_k]

        mock_reranker.rerank.side_effect = fake_rerank
        retriever = HybridRetriever(store, reranker=mock_reranker)
        return retriever, store

    def test_empty_store_returns_empty(self, tmp_path):
        retriever, _ = self._make_retriever(tmp_path)
        results = retriever.search("spring boot upgrade", repo_id="svc")
        assert results == []

    def test_search_returns_results(self, tmp_path):
        retriever, store = self._make_retriever(tmp_path)
        m = TaskMemory(
            repo_id="payment-service",
            task_pattern="Spring Boot 2.x to 3.x migration",
            description="Upgrade Spring Boot from 2.7 to 3.2",
            solution_steps=["Update pom.xml", "Replace javax with jakarta"],
            confidence=0.9,
        )
        store.upsert(m)
        results = retriever.search("spring boot migration", repo_id="payment-service")
        assert len(results) >= 1
        assert results[0].memory.id == m.id

    def test_low_confidence_filtered(self, tmp_path):
        retriever, store = self._make_retriever(tmp_path)
        m = TaskMemory(
            repo_id="svc",
            task_pattern="Some task",
            description="A low-confidence memory",
            confidence=0.05,  # below CONFIDENCE_THRESHOLD=0.2
        )
        store.upsert(m)
        results = retriever.search("some task", repo_id="svc")
        assert all(r.memory.id != m.id for r in results)
