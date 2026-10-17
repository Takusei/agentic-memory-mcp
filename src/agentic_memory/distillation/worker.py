"""Background distillation worker.

Polls the TraceStatusStore for pending/needs_redistill traces and runs the
distillation pipeline out-of-band so MCP tool calls stay fast.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone

from agentic_memory.retrieval.hybrid_retriever import HybridRetriever
from agentic_memory.schema import TaskMemory
from agentic_memory.setting import (
    HYBRID_MERGE_TOP_K,
    MERGE_THRESHOLD,
    WORKER_MAX_ATTEMPTS,
    WORKER_POLL_INTERVAL_SEC,
)
from agentic_memory.store.memory_store import MemoryStore
from agentic_memory.store.trace_status_store import (
    NEEDS_REDISTILL,
    TraceStatusStore,
)

logger = logging.getLogger(__name__)


def hybrid_merge_after_distill(
    memory: TaskMemory,
    repo_id: str,
    store: MemoryStore,
    retriever: HybridRetriever,
) -> tuple[TaskMemory, bool]:
    """Run the second-pass hybrid merge.

    The distillation pipeline uses pure vector similarity to detect
    duplicates/overlaps. Cross-channel variants (e.g. email retry → SMS retry)
    often score below that threshold despite being the same conceptual pattern.
    This re-checks via the hybrid retriever's richer signal and merges if a
    high-confidence match exists.

    Returns (final_memory, merged) where final_memory is the surviving record.
    """
    candidates = retriever.search(
        f"{memory.task_pattern}. {memory.description}",
        repo_id=repo_id,
        top_k=HYBRID_MERGE_TOP_K,
    )
    merge_candidate = next(
        (
            c
            for c in candidates
            if c.memory.id != memory.id and c.score >= MERGE_THRESHOLD
        ),
        None,
    )
    if merge_candidate is None:
        return memory, False

    target = merge_candidate.memory

    existing_pitfalls = set(target.pitfalls)
    for p in memory.pitfalls:
        if p not in existing_pitfalls:
            target.pitfalls.append(p)
            existing_pitfalls.add(p)

    existing_anchors = set(getattr(target, "lexical_anchors", []))
    for a in getattr(memory, "lexical_anchors", []):
        if a not in existing_anchors:
            target.lexical_anchors.append(a)
            existing_anchors.add(a)

    existing_paths = {kf.path for kf in target.key_files}
    for kf in memory.key_files:
        if kf.path not in existing_paths:
            target.key_files.append(kf)
            existing_paths.add(kf.path)

    if len(memory.solution_steps) > len(target.solution_steps):
        target.solution_steps = memory.solution_steps

    target.updated_at = datetime.now(timezone.utc).isoformat()
    store.upsert(target)
    store.delete(memory.id)
    logger.info(
        "Hybrid merge: new memory %s folded into existing %s (score=%.2f).",
        memory.id,
        target.id,
        merge_candidate.score,
    )
    return target, True


class DistillationWorker:
    """Polls TraceStatusStore and distills traces in a background thread."""

    def __init__(
        self,
        store: MemoryStore,
        retriever: HybridRetriever,
        status_store: TraceStatusStore,
        trace_dir: str,
        pipeline_factory,
        poll_interval: int = WORKER_POLL_INTERVAL_SEC,
        max_attempts: int = WORKER_MAX_ATTEMPTS,
    ) -> None:
        self._store = store
        self._retriever = retriever
        self._status = status_store
        self._trace_dir = trace_dir
        self._pipeline_factory = pipeline_factory
        self._poll_interval = poll_interval
        self._max_attempts = max_attempts
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        # Recover any rows orphaned by a crash mid-processing.
        requeued = self._status.requeue_orphans()
        if requeued:
            logger.info("Requeued %d orphan PROCESSING rows on startup.", requeued)
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="DistillationWorker", daemon=True
        )
        self._thread.start()
        logger.info(
            "DistillationWorker started (poll=%ds, max_attempts=%d).",
            self._poll_interval,
            self._max_attempts,
        )

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                row = self._status.claim_next()
            except sqlite3.Error as exc:
                logger.error("Worker claim_next failed: %s", exc)
                row = None

            if row is None:
                self._stop.wait(self._poll_interval)
                continue

            try:
                self.process_one(row)
            except Exception as exc:  # noqa: BLE001 - keep worker alive
                logger.exception("Worker crashed processing %s", row["trace_id"])
                self._status.mark_failed(row["trace_id"], str(exc))

    def process_one(self, row: sqlite3.Row) -> str | None:
        """Process a single claimed trace row. Returns surviving memory_id."""
        trace_id = row["trace_id"]
        note = row["note"]
        attempts = row["attempts"]

        if attempts > self._max_attempts:
            self._status.mark_failed(
                trace_id, f"exceeded max_attempts ({self._max_attempts})"
            )
            return None

        trace_path = os.path.join(self._trace_dir, f"{trace_id}.json")
        if not os.path.exists(trace_path):
            self._status.mark_failed(trace_id, f"trace file missing: {trace_path}")
            return None

        with open(trace_path) as fh:
            trace = json.load(fh)

        # Re-distillation: inject the correction note into the trace messages
        # so the LLM has context about what went wrong last time.
        if row["status"] == NEEDS_REDISTILL or note:
            if note:
                trace.setdefault("messages", []).append(
                    {"role": "assistant", "content": f"Correction note: {note}"}
                )

        pipeline = self._pipeline_factory()
        if pipeline is None:
            self._status.mark_failed(
                trace_id, "pipeline unavailable (no OPENAI_API_KEY?)"
            )
            return None

        memory, action = pipeline.run(trace)
        if memory is None:
            # Duplicate or parse failure — not an error, mark processed.
            self._status.mark_processed(trace_id, memory_id=None, action=action)
            return None

        final_memory, was_hybrid_merged = hybrid_merge_after_distill(
            memory, trace.get("repo_id", ""), self._store, self._retriever
        )
        final_action = "merged" if was_hybrid_merged else action
        self._status.mark_processed(trace_id, memory_id=final_memory.id, action=final_action)
        return final_memory.id
