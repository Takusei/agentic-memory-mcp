import logging

from agentic_memory.setting import DEFAULT_RETRIEVER_TOP_K, RERANKER_MODEL

logger = logging.getLogger(__name__)

_MODEL = RERANKER_MODEL


class Reranker:
    """Cross-encoder reranker using sentence-transformers."""

    def __init__(self) -> None:
        self._model = None  # Lazy load

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(_MODEL)
        return self._model

    def rerank(
        self, query: str, candidates: list[dict], top_k: int = DEFAULT_RETRIEVER_TOP_K
    ) -> list[dict]:
        """Rerank candidates by cross-encoder relevance score.

        Args:
            query:      The search query.
            candidates: List of dicts, each must have a "description" key (L0 text).
            top_k:      Number of top results to return.

        Returns:
            Top-k candidates sorted by rerank_score descending.
            Each dict is augmented with a "rerank_score" key.
        """
        if not candidates:
            return []

        pairs = [(query, c.get("description", "")) for c in candidates]
        try:
            scores = self.model.predict(pairs)
        except Exception as exc:
            logger.warning("Reranker.predict failed: %s; returning candidates as-is.", exc)
            for c in candidates:
                c.setdefault("rerank_score", 0.0)
            return candidates[:top_k]

        for i, c in enumerate(candidates):
            c["rerank_score"] = float(scores[i])

        return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:top_k]
