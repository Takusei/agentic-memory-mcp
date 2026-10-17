import json
import logging
from datetime import datetime

from agentic_memory.distillation.llm_distiller import distill
from agentic_memory.distillation.trace_flattener import flatten_trace
from agentic_memory.schema import KeyFile, TaskMemory
from agentic_memory.setting import (
    CROSS_PATTERN_MERGE_THRESHOLD,
    DUPLICATE_CONFIDENCE_DELTA,
    DUPLICATE_THRESHOLD,
    OVERLAP_THRESHOLD,
)
from agentic_memory.store.memory_store import MemoryStore

logger = logging.getLogger(__name__)

_DUPLICATE_THRESHOLD = DUPLICATE_THRESHOLD
_OVERLAP_THRESHOLD = OVERLAP_THRESHOLD
_CROSS_PATTERN_MERGE_THRESHOLD = CROSS_PATTERN_MERGE_THRESHOLD


def _dict_to_memory(extracted: dict, trace: dict) -> TaskMemory:
    """Convert LLM-extracted dict + original trace metadata into a TaskMemory.

    Handles missing/malformed fields gracefully.
    """
    raw_key_files = extracted.get("key_files", [])
    key_files: list[KeyFile] = []
    for kf in raw_key_files:
        if isinstance(kf, str):
            key_files.append(KeyFile(path=kf))
        elif isinstance(kf, dict):
            key_files.append(KeyFile(**kf))

    return TaskMemory(
        repo_id=trace.get("repo_id", ""),
        task_pattern=extracted.get("task_pattern", ""),
        description=extracted.get("description", ""),
        key_files=key_files,
        solution_steps=extracted.get("solution_steps", []),
        pitfalls=extracted.get("pitfalls", []),
        outcome=extracted.get("outcome", "success"),
        lexical_anchors=extracted.get("lexical_anchors", []),
        source_trace_id=trace.get("trace_id", ""),
    )


class DistillationPipeline:
    """Orchestrates: flatten → distill → dedup → upsert."""

    def __init__(self, memory_store: MemoryStore, llm) -> None:
        self.memory_store = memory_store
        self.llm = llm

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self, trace: dict) -> tuple[TaskMemory | None, str]:
        """Full pipeline for a single trace.

        Returns (memory, action) where action is one of:
          "created"   — new memory stored
          "merged"    — new content folded into an existing memory
          "duplicate" — near-identical memory already exists; confidence reinforced
          "failed"    — distillation failed or yielded no usable output
        """
        flattened = flatten_trace(trace)
        try:
            extracted = distill(flattened, self.llm)
        except (ValueError, json.JSONDecodeError) as exc:
            logger.error(
                "Distillation failed for trace %s: %s", trace.get("trace_id"), exc
            )
            return None, "failed"

        memory = _dict_to_memory(extracted, trace)

        if not memory.task_pattern:
            logger.warning("Distilled memory has empty task_pattern; skipping.")
            return None, "failed"

        action, existing_id = self._dedup_check(memory)

        if action == "duplicate":
            logger.info(
                "Duplicate memory for '%s'; reinforcing %s.",
                memory.task_pattern,
                existing_id,
            )
            self.memory_store.update_confidence(
                existing_id, delta=DUPLICATE_CONFIDENCE_DELTA
            )
            existing = self.memory_store.get(existing_id)
            if existing:
                existing.reinforcement_count += 1
                self.memory_store.upsert(existing)
            return None, "duplicate"

        if action == "overlap":
            logger.info(
                "Overlapping memory for '%s'; merging into %s.",
                memory.task_pattern,
                existing_id,
            )
            self._merge(existing_id, memory)
            return self.memory_store.get(existing_id), "merged"

        # Novel
        logger.info(
            "Novel memory distilled: '%s' (id=%s).", memory.task_pattern, memory.id
        )
        self.memory_store.upsert(memory)
        return memory, "created"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _dedup_check(self, memory: TaskMemory) -> tuple[str, str]:
        """Check whether an equivalent or overlapping memory already exists.

        Returns:
            A 2-tuple (action, existing_id) where action is one of:
            "duplicate", "overlap", "novel".
            existing_id is "" when action == "novel".
        """
        # Build P1 text the same way MemoryStore does for passage "task"
        prefix = memory.repo_id or "global"
        p1_text = f"{prefix} | {memory.task_pattern}. {memory.description}".strip(" |.")

        candidates = self.memory_store.vector_store.search(
            query=p1_text,
            repo_id=memory.repo_id or None,
            top_k=3,
        )
        if not candidates:
            return ("novel", "")

        # Find the first candidate that isn't a self-match
        top = None
        for candidate in candidates:
            if candidate["memory_id"] != memory.id:
                top = candidate
                break

        if top is None:
            return ("novel", "")

        score = top["score"]
        existing_id = top["memory_id"]

        if score >= _DUPLICATE_THRESHOLD:
            return ("duplicate", existing_id)
        if score >= _OVERLAP_THRESHOLD:
            # Option 2:
            # - Merge at normal overlap only for same task_pattern.
            # - For different task_pattern, allow merge only at very high similarity.
            existing = self.memory_store.get(existing_id)
            if existing and existing.task_pattern == memory.task_pattern:
                return ("overlap", existing_id)

            if existing and score >= _CROSS_PATTERN_MERGE_THRESHOLD:
                logger.info(
                    "Cross-pattern high-similarity merge: new='%s' existing='%s' score=%.3f",
                    memory.task_pattern,
                    existing.task_pattern,
                    score,
                )
                return ("overlap", existing_id)

        return ("novel", "")

    def _merge(self, existing_id: str, new_memory: TaskMemory) -> None:
        """Merge new pitfalls/steps into the existing memory and re-upsert."""
        existing = self.memory_store.get(existing_id)
        if existing is None:
            logger.warning("Cannot merge: existing memory %s not found.", existing_id)
            self.memory_store.upsert(new_memory)
            return

        # Append pitfalls not already present (exact string match)
        existing_pitfall_set = set(existing.pitfalls)
        for pitfall in new_memory.pitfalls:
            if pitfall not in existing_pitfall_set:
                existing.pitfalls.append(pitfall)
                existing_pitfall_set.add(pitfall)

        # Update solution steps if new memory has more detail
        if len(new_memory.solution_steps) > len(existing.solution_steps):
            existing.solution_steps = new_memory.solution_steps

        # Merge lexical anchors
        existing_anchors = set(existing.lexical_anchors)
        for anchor in new_memory.lexical_anchors:
            if anchor not in existing_anchors:
                existing.lexical_anchors.append(anchor)
                existing_anchors.add(anchor)

        existing.updated_at = datetime.utcnow().isoformat()
        self.memory_store.upsert(existing)
