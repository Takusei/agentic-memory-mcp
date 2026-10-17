import logging
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from agentic_memory.setting import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PERSIST_DIR,
    CHROMA_SPACE,
    EMBEDDING_MODEL,
    RETRIEVAL_CANDIDATE_TOP_K,
)

logger = logging.getLogger(__name__)

_COLLECTION_NAME = CHROMA_COLLECTION_NAME
_EMBEDDING_MODEL = EMBEDDING_MODEL


class VectorStore:
    """ChromaDB-backed vector store for TaskMemory passages."""

    def __init__(self, persist_dir: str | None = None) -> None:
        persist_dir = persist_dir or CHROMA_PERSIST_DIR
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._ef = SentenceTransformerEmbeddingFunction(model_name=_EMBEDDING_MODEL)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=self._ef,
            metadata={"hnsw:space": CHROMA_SPACE},
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert_passages(
        self,
        memory_id: str,
        passages: dict[str, str],
        repo_id: str,
    ) -> None:
        """Upsert up to 4 passage documents for a single memory.

        Args:
            memory_id: Unique memory identifier.
            passages:  Mapping of passage_type → passage text.
                       Keys: "task", "files", "steps", "pitfalls".
            repo_id:   Repository identifier stored as metadata for filtering.
        """
        ids = []
        documents = []
        metadatas = []

        for passage_type, text in passages.items():
            if not text.strip():
                continue
            ids.append(f"{memory_id}_{passage_type}")
            documents.append(text)
            metadatas.append(
                {"memory_id": memory_id, "passage_type": passage_type, "repo_id": repo_id}
            )

        if ids:
            self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def delete(self, memory_id: str) -> None:
        """Delete all passage documents belonging to *memory_id*."""
        passage_types = ("task", "files", "steps", "pitfalls")
        ids_to_delete = [f"{memory_id}_{pt}" for pt in passage_types]
        # ChromaDB silently ignores IDs that don't exist — safe to call unconditionally
        try:
            self._collection.delete(ids=ids_to_delete)
        except Exception as exc:  # pragma: no cover
            logger.warning("VectorStore.delete error for %s: %s", memory_id, exc)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        repo_id: str | None = None,
        top_k: int = RETRIEVAL_CANDIDATE_TOP_K,
    ) -> list[dict]:
        """Search for passages similar to *query*.

        Args:
            query:   Free-text search query.
            repo_id: If given, restrict results to this repository.
            top_k:   Maximum number of results.

        Returns:
            List of dicts with keys: memory_id, passage_type, score, text.
            score is cosine similarity (0–1; higher = more similar).
        """
        count = self._collection.count()
        if count == 0:
            return []

        effective_k = min(top_k, count)
        kwargs: dict = {"query_texts": [query], "n_results": effective_k, "include": ["documents", "metadatas", "distances"]}
        if repo_id:
            kwargs["where"] = {"repo_id": repo_id}

        try:
            results = self._collection.query(**kwargs)
        except Exception as exc:
            logger.warning("VectorStore.search error: %s", exc)
            return []

        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # ChromaDB cosine distance ∈ [0, 2]; similarity = 1 - distance/2
            # But with hnsw:space=cosine, distance = 1 - cosine_sim, so sim = 1 - dist
            score = max(0.0, 1.0 - dist)
            output.append(
                {
                    "memory_id": meta["memory_id"],
                    "passage_type": meta["passage_type"],
                    "score": score,
                    "text": doc,
                }
            )
        return output
