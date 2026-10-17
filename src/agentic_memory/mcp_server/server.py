"""FastMCP server exposing all agentic-memory tools.

Start with:
    uv run python -m agentic_memory.mcp_server.server
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

from agentic_memory.distillation.pipeline import DistillationPipeline
from agentic_memory.distillation.worker import DistillationWorker
from agentic_memory.forgetting.worker import ForgettingWorker
from agentic_memory.retrieval.hybrid_retriever import HybridRetriever
from agentic_memory.retrieval.progressive import format_at_level
from agentic_memory.schema import KeyFile, TaskMemory
from agentic_memory.setting import (
    CORRECT_CONFIDENCE_DELTA,
    DEFAULT_LOOKUP_TOP_K,
    DISTILL_MODEL,
    DISTILL_TEMPERATURE,
    FORGET_ENABLED,
    INCORRECT_CONFIDENCE_DELTA,
    MAX_MEMORY_NOTES,
    PARTIAL_CONFIDENCE_DELTA,
    TRACE_DIR,
    TRACE_STATUS_DB_PATH,
    WORKER_ENABLED,
)
from agentic_memory.store.memory_store import MemoryStore
from agentic_memory.store.trace_status_store import PROCESSED, TraceStatusStore

logger = logging.getLogger(__name__)

mcp = FastMCP("agentic-memory")
store = MemoryStore()
retriever = HybridRetriever(store)
status_store = TraceStatusStore(TRACE_STATUS_DB_PATH)


# ---------------------------------------------------------------------------
# Tool: memory_lookup
# ---------------------------------------------------------------------------


@mcp.tool()
def memory_lookup(
    task: str, repo_id: str, top_k: int = DEFAULT_LOOKUP_TOP_K
) -> list[dict]:
    """Search for relevant task memories.

    Returns L0 results (id, task_pattern, description, confidence, score).
    Call memory_get(id, level="L1") to see key files and step/pitfall counts.
    Call memory_get(id, level="L2") only if L1 is insufficient for the task.

    Args:
        task:    Natural language description of the current task.
        repo_id: Repository identifier. Used for repo-scoped search first,
                 then cross-repo fallback if repo results < top_k.
        top_k:   Maximum number of results to return (default 5).
    """
    results = retriever.search(task, repo_id=repo_id, top_k=top_k)
    items = []
    for result in results:
        item = format_at_level(result.memory, result.score, level="L0")
        item["cross_repo"] = result.cross_repo
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Tool: memory_get
# ---------------------------------------------------------------------------


@mcp.tool()
def memory_get(memory_id: str, level: str = "L1") -> dict | None:
    """Retrieve a memory by ID at the requested disclosure level.

    Default is L1 to support progressive disclosure.
    Use L2 only when detailed steps/pitfalls are needed.

    Args:
        memory_id: Memory ID returned by memory_lookup.
        level:     "L0" (abstract only), "L1" (files + step count, default), or "L2" (full detail).
    """
    memory = store.get(memory_id)
    if memory is None:
        return None
    return format_at_level(memory, score=0.0, level=level)


# ---------------------------------------------------------------------------
# Tool: memory_rate
# ---------------------------------------------------------------------------


@mcp.tool()
def memory_rate(
    memory_id: str,
    factual: str | None = None,
    relevance: str | None = None,
    note: str | None = None,
) -> dict:
    """Rate a retrieved memory after use. Drives the feedback loop.

    Args:
        memory_id: Memory ID to rate.
        factual:   "correct" | "incorrect" | "partially_correct"
        relevance: "relevant" | "irrelevant"
        note:      Optional free-text note.

    When factual="incorrect", the memory's source trace is re-queued for
    distillation and the response includes ``redistill_trace_id``. Pass that ID
    to ``memory_trace_status`` to see the re-distillation outcome
    (created / merged / duplicate).
    """
    memory = store.get(memory_id)
    if memory is None:
        return {"ok": False, "error": "not found"}

    delta = 0.0
    needs_redistillation = False

    if factual == "correct":
        delta = CORRECT_CONFIDENCE_DELTA
        memory.use_count += 1
        memory.reinforcement_count += 1
        memory.last_used_at = datetime.now(timezone.utc).isoformat()
    elif factual == "incorrect":
        delta = INCORRECT_CONFIDENCE_DELTA
        needs_redistillation = True
        memory.decay_count += 1
    elif factual == "partially_correct":
        delta = PARTIAL_CONFIDENCE_DELTA
        memory.decay_count += 1

    if relevance == "irrelevant":
        logger.info("Irrelevant memory logged for retrieval tuning: %s", memory_id)

    new_confidence = max(0.0, min(1.0, memory.confidence + delta))

    if note:
        memory.notes.append(note[:200])
        memory.notes = memory.notes[-MAX_MEMORY_NOTES:]

    # Persist updated counts and notes first
    store.upsert(memory)

    # Then apply confidence delta (update_confidence re-reads the file)
    if delta != 0.0:
        store.update_confidence(memory_id, delta)

    redistill_queued = False
    redistill_trace_id = None
    if needs_redistillation and memory.source_trace_id:
        # Flip the source trace to needs_redistill; the background worker
        # picks it up next cycle. The full LLM round-trip stays out of the
        # MCP tool response so callers don't block on it.
        if status_store.mark_needs_redistill(memory.source_trace_id, note):
            redistill_queued = True
            redistill_trace_id = memory.source_trace_id
        else:
            logger.warning(
                "Cannot flag re-distillation: no status row for trace %s.",
                memory.source_trace_id,
            )

    return {
        "ok": True,
        "new_confidence": new_confidence,
        "redistill_queued": redistill_queued,
        "redistill_trace_id": redistill_trace_id,
    }


# ---------------------------------------------------------------------------
# Tool: memory_add
# ---------------------------------------------------------------------------


@mcp.tool()
def memory_add(
    repo_id: str,
    task_pattern: str,
    description: str,
    key_files: list[str],
    solution_steps: list[str],
    pitfalls: list[str],
    outcome: str = "success",
) -> dict:
    """Agent-initiated memory write.

    Use when you discover something reusable mid-session.

    Args:
        repo_id:        Repository this memory belongs to.
        task_pattern:   Short label for the task class.
        description:    One-sentence abstract (used as L0).
        key_files:      List of essential file paths.
        solution_steps: Ordered steps to solve this class of task.
        pitfalls:       Pitfalls or surprises to warn future agents about.
        outcome:        "success" | "partial" | "failure"
    """
    memory = TaskMemory(
        repo_id=repo_id,
        task_pattern=task_pattern,
        description=description,
        key_files=[KeyFile(path=p) for p in key_files],
        solution_steps=solution_steps,
        pitfalls=pitfalls,
        outcome=outcome,
        source_trace_id="agent-initiated",
    )
    store.upsert(memory)
    return {"ok": True, "memory_id": memory.id}


# ---------------------------------------------------------------------------
# Tool: memory_update
# ---------------------------------------------------------------------------


@mcp.tool()
def memory_update(
    memory_id: str,
    description: str | None = None,
    key_files: list[str] | None = None,
    solution_steps: list[str] | None = None,
    pitfalls: list[str] | None = None,
    outcome: str | None = None,
) -> dict:
    """Update specific fields of an existing memory.

    Accepted fields: description, key_files (list[str]),
    solution_steps, pitfalls, outcome.
    """
    memory = store.get(memory_id)
    if memory is None:
        return {"ok": False, "error": "not found"}

    if description is not None:
        memory.description = description
    if key_files is not None:
        memory.key_files = [KeyFile(path=p) for p in key_files]
    if solution_steps is not None:
        memory.solution_steps = solution_steps
    if pitfalls is not None:
        memory.pitfalls = pitfalls
    if outcome is not None:
        memory.outcome = outcome

    memory.updated_at = datetime.now(timezone.utc).isoformat()
    store.upsert(memory)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Tool: memory_delete
# ---------------------------------------------------------------------------


@mcp.tool()
def memory_delete(memory_id: str) -> dict:
    """Delete a memory from the knowledge store.

    Use when a memory is confirmed stale.
    """
    if store.get(memory_id) is None:
        return {"ok": False, "error": "not found"}
    store.delete(memory_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Lazy LLM + pipeline (only instantiated when memory_save_trace is called)
# ---------------------------------------------------------------------------

_pipeline: DistillationPipeline | None = None
_TRACE_DIR = TRACE_DIR


def _get_pipeline() -> DistillationPipeline | None:
    """Return a DistillationPipeline if OPENAI_API_KEY is set, else None."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        llm = ChatOpenAI(model=DISTILL_MODEL, temperature=DISTILL_TEMPERATURE)
        _pipeline = DistillationPipeline(memory_store=store, llm=llm)
        return _pipeline
    except Exception as exc:
        logger.warning("Could not initialise distillation pipeline: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Tool: memory_save_trace
# ---------------------------------------------------------------------------


@mcp.tool()
def memory_save_trace(
    repo_id: str,
    task: str,
    messages: list[dict],
    trace_id: str | None = None,
) -> dict:
    """Persist a task execution trace from the current session as a memory trace.

    Call this at the END of every task. The trace is written to disk and
    enqueued for the background distillation worker; this call returns
    immediately without waiting for the LLM.

    Args:
        repo_id:   Repository the task was performed on (e.g. "payment-service").
        task:      One-sentence description of what was asked.
        messages:  List of dicts with "role" and "content" keys capturing the
                   plans, tool calls, key outputs, final result, and concise
                   rationale from the session.  Accepted roles:
                     "assistant" — concise rationale / plan summary
                     "tool"      — tool call, e.g. "read_file(src/pom.xml)"
                     "result"    — output of the tool call (truncated is fine)
                     "final"     — final answer / conclusion
        trace_id:  Optional. Auto-generated if not provided.

    Example messages::

        [
          {"role": "assistant", "content": "I'll look at pom.xml first."},
          {"role": "tool",      "content": "read_file(pom.xml)"},
          {"role": "result",    "content": "<parent>spring-boot 2.7.0</parent>"},
          {"role": "final",     "content": "Updated parent POM to 3.2.0."}
        ]
    """
    tid = trace_id or str(uuid.uuid4())
    trace = {
        "trace_id": tid,
        "repo_id": repo_id,
        "task": task,
        "messages": messages,
    }

    # Always persist raw trace to disk so it can be distilled later.
    trace_path = os.path.join(_TRACE_DIR, f"{tid}.json")
    os.makedirs(_TRACE_DIR, exist_ok=True)
    with open(trace_path, "w") as fh:
        json.dump(trace, fh, indent=2)
    logger.info("Trace %s saved to %s", tid, trace_path)

    # Enqueue for the background distillation worker. Distillation no longer
    # happens inline so this tool call returns immediately regardless of
    # whether an LLM is configured.
    status_store.enqueue(tid)
    return {
        "ok": True,
        "trace_id": tid,
        "status": "pending",
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _backfill_existing_traces() -> int:
    """Mark any on-disk traces missing from the status DB as PROCESSED.

    Prevents the worker from re-distilling history on first run.
    """
    trace_dir = Path(_TRACE_DIR)
    if not trace_dir.exists():
        return 0
    inserted = 0
    for trace_file in trace_dir.glob("*.json"):
        tid = trace_file.stem
        if status_store.get(tid) is None:
            status_store.enqueue(tid, status=PROCESSED)
            inserted += 1
    if inserted:
        logger.info("Backfilled %d existing trace(s) as processed.", inserted)
    return inserted


_worker: DistillationWorker | None = None


def _start_worker() -> DistillationWorker | None:
    global _worker
    if not WORKER_ENABLED:
        logger.info("Distillation worker disabled (WORKER_ENABLED=false).")
        return None
    _worker = DistillationWorker(
        store=store,
        retriever=retriever,
        status_store=status_store,
        trace_dir=_TRACE_DIR,
        pipeline_factory=_get_pipeline,
    )
    _worker.start()
    logger.info("Distillation worker started.")
    return _worker


_forgetting_worker: ForgettingWorker | None = None


def _start_forgetting_worker() -> ForgettingWorker | None:
    global _forgetting_worker
    if not FORGET_ENABLED:
        logger.info("Forgetting worker disabled (FORGET_ENABLED=false).")
        return None
    _forgetting_worker = ForgettingWorker(store=store)
    _forgetting_worker.start()
    logger.info("Forgetting worker started.")
    return _forgetting_worker


# ---------------------------------------------------------------------------
# Tool: memory_trace_status
# ---------------------------------------------------------------------------


@mcp.tool()
def memory_trace_status(trace_id: str) -> dict | None:
    """Return the distillation status of a saved trace.

    Call this after memory_save_trace to see whether the background worker has
    processed the trace and what the outcome was.

    Returns a dict with fields:
        trace_id       — the trace ID
        status         — "pending" | "processing" | "processed" | "failed" | "needs_redistill"
        distill_action — "created" | "merged" | "duplicate" | "failed" | "unknown"
        memory_id      — the resulting memory ID, or null if duplicate/failed
        attempts       — number of processing attempts
        last_error     — error message if status is "failed", else null
        updated_at     — ISO timestamp of last status change

    Returns null if the trace_id is not found.
    """
    row = status_store.get(trace_id)
    if row is None:
        return None
    return {
        "trace_id": row["trace_id"],
        "status": row["status"],
        "distill_action": row["distill_action"],
        "memory_id": row["memory_id"],
        "attempts": row["attempts"],
        "last_error": row["last_error"],
        "updated_at": row["updated_at"],
    }


# ---------------------------------------------------------------------------
# Tool: memory_worker_status
# ---------------------------------------------------------------------------


@mcp.tool()
def memory_worker_status() -> dict:
    """Return the current status of the background workers.

    Reports whether the distillation and forgetting worker threads are running,
    whether an LLM pipeline is available, a summary of trace queue counts, and
    the last forgetting sweep result.
    """
    thread_alive = (
        _worker is not None
        and _worker._thread is not None
        and _worker._thread.is_alive()
    )
    forgetting_alive = (
        _forgetting_worker is not None
        and _forgetting_worker._thread is not None
        and _forgetting_worker._thread.is_alive()
    )
    counts = status_store.counts()
    return {
        "worker_enabled": WORKER_ENABLED,
        "worker_running": thread_alive,
        "pipeline_available": bool(os.getenv("OPENAI_API_KEY")),
        "queue": counts,
        "forgetting_enabled": FORGET_ENABLED,
        "forgetting_running": forgetting_alive,
        "forgetting_last_sweep": (
            _forgetting_worker.last_sweep if _forgetting_worker else None
        ),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _backfill_existing_traces()
    _start_worker()
    _start_forgetting_worker()
    mcp.run(transport="stdio")
