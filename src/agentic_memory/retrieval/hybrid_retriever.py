import logging

from agentic_memory.retrieval.query_reformulator import QueryReformulator
from agentic_memory.retrieval.reranker import Reranker
from agentic_memory.schema import RetrievalResult
from agentic_memory.setting import (
    CONFIDENCE_THRESHOLD,
    CROSS_REPO_SCORE_THRESHOLD,
    DEFAULT_RETRIEVER_TOP_K,
    RETRIEVAL_CANDIDATE_TOP_K,
    RRF_K,
    RRF_OUTPUT_LIMIT,
)
from agentic_memory.store.memory_store import MemoryStore

logger = logging.getLogger(__name__)

_RRF_K = RRF_K
_CONFIDENCE_THRESHOLD = CONFIDENCE_THRESHOLD


def rrf_fusion(
    bm25_results: list[dict],
    vector_results: list[dict],
    k: int = _RRF_K,
) -> list[dict]:
    """Reciprocal Rank Fusion of BM25 and vector result lists.

    Deduplicates by memory_id (highest-ranked passage wins).
    Returns merged list sorted by fused score, top 30.

    Args:
        bm25_results:   List of dicts with "memory_id" key (sorted best-first).
        vector_results: List of dicts with "memory_id" key (sorted best-first).
        k:              RRF constant (default 60).

    Returns:
        List of {"memory_id": str, "rrf_score": float} sorted descending.
    """
    scores: dict[str, float] = {}

    for rank, result in enumerate(bm25_results):
        mid = result["memory_id"]
        scores[mid] = scores.get(mid, 0.0) + 1.0 / (k + rank + 1)

    for rank, result in enumerate(vector_results):
        mid = result["memory_id"]
        scores[mid] = scores.get(mid, 0.0) + 1.0 / (k + rank + 1)

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [
        {"memory_id": mid, "rrf_score": scores[mid]}
        for mid in sorted_ids[:RRF_OUTPUT_LIMIT]
    ]


class HybridRetriever:
    """Hybrid BM25 + vector retriever with RRF fusion and cross-encoder reranking."""

    def __init__(
        self,
        memory_store: MemoryStore,
        reformulator: QueryReformulator | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self._store = memory_store
        self._reformulator = reformulator or QueryReformulator()
        self._reranker = reranker or Reranker()

    def search(
        self,
        query: str,
        repo_id: str = "",
        top_k: int = DEFAULT_RETRIEVER_TOP_K,
    ) -> list[RetrievalResult]:
        """Full hybrid search pipeline.

        1. Optional query reformulation.
        2. Parallel BM25 + vector search (repo-scoped first, cross-repo fallback).
        3. RRF fusion.
        4. Confidence filtering.
        5. Cross-encoder reranking.
        6. Load full memories and return RetrievalResult list.

        Args:
            query:   Natural language task description.
            repo_id: Repository identifier for scoped search.
            top_k:   Maximum results to return.

        Returns:
            List of RetrievalResult (memory + score), best-first.
        """
        # 1. Optional reformulation
        search_query = self._reformulator.reformulate(query)

        # 2a. Repo-scoped search
        bm25 = self._store.bm25_store.search(
            search_query, repo_id=repo_id or None, top_k=RETRIEVAL_CANDIDATE_TOP_K
        )
        vec = self._store.vector_store.search(
            search_query, repo_id=repo_id or None, top_k=RETRIEVAL_CANDIDATE_TOP_K
        )

        # 2b. Cross-repo fallback if results are sparse or low-quality
        cross_repo_ids: set[str] = set()
        top_vec_score = max((r["score"] for r in vec), default=0.0)
        results_sparse = len({r["memory_id"] for r in bm25 + vec}) < top_k
        results_low_quality = top_vec_score < CROSS_REPO_SCORE_THRESHOLD
        if (results_sparse or results_low_quality) and repo_id:
            extra_bm25 = self._store.bm25_store.search(
                search_query, repo_id=None, top_k=top_k
            )
            extra_vec = self._store.vector_store.search(
                search_query, repo_id=None, top_k=top_k
            )
            # Only add new memory_ids not already in repo-scoped results
            repo_ids = {r["memory_id"] for r in bm25 + vec}
            for r in extra_bm25 + extra_vec:
                if r["memory_id"] not in repo_ids:
                    cross_repo_ids.add(r["memory_id"])
            bm25 = bm25 + [r for r in extra_bm25 if r["memory_id"] in cross_repo_ids]
            vec = vec + [r for r in extra_vec if r["memory_id"] in cross_repo_ids]

        # 3. RRF fusion
        fused = rrf_fusion(bm25, vec)

        # 4. Load L0 descriptions and apply confidence filter
        candidates = []
        seen_ids: set[str] = set()
        for item in fused:
            mid = item["memory_id"]
            if mid in seen_ids:
                continue
            seen_ids.add(mid)
            memory = self._store.get(mid)
            if memory is None:
                continue
            if memory.confidence <= _CONFIDENCE_THRESHOLD:
                continue
            candidates.append(
                {
                    "memory_id": mid,
                    "rrf_score": item["rrf_score"],
                    "description": memory.description,  # Todo: consider richer passage text for reranking
                    "cross_repo": mid in cross_repo_ids,
                }
            )

        if not candidates:
            return []

        # 5. Rerank
        reranked = self._reranker.rerank(query, candidates, top_k=top_k)

        # 6. Build RetrievalResult list
        results: list[RetrievalResult] = []
        for item in reranked:
            memory = self._store.get(item["memory_id"])
            if memory:
                results.append(
                    RetrievalResult(
                        memory=memory,
                        score=item["rerank_score"],
                        cross_repo=item.get("cross_repo", False),
                    )
                )
        return results
