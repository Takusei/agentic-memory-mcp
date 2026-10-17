import logging
import pickle
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from agentic_memory.setting import MEMORY_DATA_DIR, RETRIEVAL_CANDIDATE_TOP_K

logger = logging.getLogger(__name__)

_DEFAULT_INDEX_PATH = "./data/bm25_index.pkl"


def _tokenize(text: str) -> list[str]:
    """Lowercase + split on non-word characters."""
    return [t for t in re.split(r"\W+", text.lower()) if t]


class BM25Store:
    """BM25 (Okapi) index over TaskMemory passages, persisted via pickle."""

    def __init__(self, index_path: str | None = None) -> None:
        self._index_path = Path(
            index_path or Path(MEMORY_DATA_DIR) / "bm25_index.pkl"
        )
        # Each record: {memory_id, passage_type, repo_id, text, tokens}
        self._docs: list[dict] = []
        self._bm25: BM25Okapi | None = None
        self.load()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert(
        self,
        memory_id: str,
        passages: dict[str, str],
        repo_id: str,
    ) -> None:
        """Insert or replace passages for *memory_id* and rebuild the index."""
        # Remove existing docs for this memory
        self._docs = [d for d in self._docs if d["memory_id"] != memory_id]

        for passage_type, text in passages.items():
            if not text.strip():
                continue
            self._docs.append(
                {
                    "memory_id": memory_id,
                    "passage_type": passage_type,
                    "repo_id": repo_id,
                    "text": text,
                    "tokens": _tokenize(text),
                }
            )

        self._rebuild()
        self.save()

    def delete(self, memory_id: str) -> None:
        """Remove all passages for *memory_id* and rebuild the index."""
        self._docs = [d for d in self._docs if d["memory_id"] != memory_id]
        self._rebuild()
        self.save()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        repo_id: str | None = None,
        top_k: int = RETRIEVAL_CANDIDATE_TOP_K,
    ) -> list[dict]:
        """BM25 search over passage corpus.

        Returns list of dicts: {memory_id, passage_type, bm25_score, text}.
        """
        if not self._docs or self._bm25 is None:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)

        # Build (score, doc_index) pairs, optionally filtered by repo_id
        pairs = []
        for idx, doc in enumerate(self._docs):
            if repo_id and doc["repo_id"] != repo_id:
                continue
            pairs.append((scores[idx], idx))

        if not pairs:
            return []

        pairs.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, idx in pairs[:top_k]:
            doc = self._docs[idx]
            results.append(
                {
                    "memory_id": doc["memory_id"],
                    "passage_type": doc["passage_type"],
                    "bm25_score": float(score),
                    "text": doc["text"],
                }
            )
        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist the raw document list to disk."""
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._index_path, "wb") as f:
            pickle.dump(self._docs, f)

    def load(self) -> None:
        """Load raw documents from disk and rebuild the BM25 index."""
        if self._index_path.exists():
            try:
                with open(self._index_path, "rb") as f:
                    self._docs = pickle.load(f)
                self._rebuild()
            except Exception as exc:
                logger.warning("BM25Store.load failed (%s); starting empty.", exc)
                self._docs = []
                self._bm25 = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        """Rebuild BM25Okapi from current self._docs."""
        if not self._docs:
            self._bm25 = None
            return
        corpus = [doc["tokens"] for doc in self._docs]
        self._bm25 = BM25Okapi(corpus)
