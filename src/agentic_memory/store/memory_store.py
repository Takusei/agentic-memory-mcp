import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from agentic_memory.schema import KeyFile, TaskMemory
from agentic_memory.setting import MEMORY_DATA_DIR
from agentic_memory.store.bm25_store import BM25Store
from agentic_memory.store.vector_store import VectorStore

logger = logging.getLogger(__name__)


def _build_passages(memory: TaskMemory) -> dict[str, str]:
    """Construct the 4 indexable passages from a TaskMemory.

    Prefix format: "{repo_id} | {content}"
    """
    prefix = memory.repo_id or "global"

    p1 = f"{prefix} | {memory.task_pattern}. {memory.description}".strip(" |.")
    p2_body = " ".join(kf.path for kf in memory.key_files)
    p2 = f"{prefix} | {p2_body}".strip(" |") if p2_body else ""
    p3_body = " ".join(memory.solution_steps)
    p3 = f"{prefix} | {p3_body}".strip(" |") if p3_body else ""
    p4_body = " ".join(memory.pitfalls)
    p4 = f"{prefix} | {p4_body}".strip(" |") if p4_body else ""

    passages: dict[str, str] = {"task": p1}
    if p2:
        passages["files"] = p2
    if p3:
        passages["steps"] = p3
    if p4:
        passages["pitfalls"] = p4
    return passages


def _memory_to_dict(memory: TaskMemory) -> dict:
    """Serialize a TaskMemory to a plain dict (JSON-safe)."""
    d = memory.__dict__.copy()
    d["key_files"] = [kf.__dict__ for kf in memory.key_files]
    return d


def _memory_from_dict(data: dict) -> TaskMemory:
    """Deserialize a dict (from JSON) back to a TaskMemory."""
    key_files = [KeyFile(**kf) for kf in data.pop("key_files", [])]
    data.setdefault("notes", [])  # back-compat: old JSON files lack this field
    memory = TaskMemory(**data)
    memory.key_files = key_files
    return memory


class MemoryStore:
    """Unified read/write API over vector store, BM25, and JSON files."""

    def __init__(
        self,
        data_dir: str | None = None,
        vector_store: VectorStore | None = None,
        bm25_store: BM25Store | None = None,
    ) -> None:
        data_dir = data_dir or MEMORY_DATA_DIR
        self._memories_dir = Path(data_dir) / "memories"
        self._memories_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir = Path(data_dir) / "archive"

        self._vector_store = vector_store or VectorStore(
            persist_dir=str(Path(data_dir) / "chroma")
        )
        self._bm25_store = bm25_store or BM25Store(
            index_path=str(Path(data_dir) / "bm25_index.pkl")
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert(self, memory: TaskMemory) -> None:
        """Persist a memory to JSON and index it in both stores."""
        # 1. Write JSON
        path = self._memories_dir / f"{memory.id}.json"
        with open(path, "w") as f:
            json.dump(_memory_to_dict(memory), f, indent=2)

        # 2. Build passages
        passages = _build_passages(memory)

        # 3. Index in both stores
        self._vector_store.upsert_passages(memory.id, passages, memory.repo_id)
        self._bm25_store.upsert(memory.id, passages, memory.repo_id)

    def update_confidence(self, memory_id: str, delta: float) -> None:
        """Adjust a memory's confidence by *delta*, clamped to [0.0, 1.0]."""
        memory = self.get(memory_id)
        if memory is None:
            logger.warning("update_confidence: memory %s not found", memory_id)
            return
        memory.confidence = max(0.0, min(1.0, memory.confidence + delta))
        memory.updated_at = datetime.now(timezone.utc).isoformat()
        self.upsert(memory)

    def delete(self, memory_id: str) -> None:
        """Remove a memory from JSON and both indexes."""
        path = self._memories_dir / f"{memory_id}.json"
        if path.exists():
            path.unlink()
        self._vector_store.delete(memory_id)
        self._bm25_store.delete(memory_id)

    def archive(self, memory_id: str, reason: str) -> bool:
        """Soft-delete a memory: move it to the archive dir and de-index it.

        The memory's JSON is stamped with ``archived_at`` / ``forget_reason`` and
        written to :data:`MEMORY_ARCHIVE_DIR`, then removed from the live store and
        both search indexes. The archived copy is recoverable; nothing is purged.

        Returns True if a memory was archived, False if it did not exist.
        """
        memory = self.get(memory_id)
        if memory is None:
            logger.warning("archive: memory %s not found", memory_id)
            return False

        memory.archived_at = datetime.now(timezone.utc).isoformat()
        memory.forget_reason = reason

        self._archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = self._archive_dir / f"{memory_id}.json"
        with open(archive_path, "w") as f:
            json.dump(_memory_to_dict(memory), f, indent=2)

        # Remove from live store + both indexes.
        self.delete(memory_id)
        logger.info("Archived memory %s (reason=%s)", memory_id, reason)
        return True

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, memory_id: str) -> TaskMemory | None:
        """Load a memory by ID from JSON, or None if not found."""
        path = self._memories_dir / f"{memory_id}.json"
        if not path.exists():
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            return _memory_from_dict(data)
        except Exception as exc:
            logger.error("MemoryStore.get failed for %s: %s", memory_id, exc)
            return None

    def list_all(self, repo_id: str | None = None) -> list[TaskMemory]:
        """Return all stored memories, optionally filtered by repo_id."""
        memories = []
        for path in self._memories_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                memory = _memory_from_dict(data)
                if repo_id is None or memory.repo_id == repo_id:
                    memories.append(memory)
            except Exception as exc:
                logger.warning("Skipping malformed memory file %s: %s", path, exc)
        return memories

    # ------------------------------------------------------------------
    # Accessors (for pipeline / retrieval to use directly)
    # ------------------------------------------------------------------

    @property
    def vector_store(self) -> VectorStore:
        return self._vector_store

    @property
    def bm25_store(self) -> BM25Store:
        return self._bm25_store
