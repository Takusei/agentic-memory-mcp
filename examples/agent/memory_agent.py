"""Memory-augmented LangChain agent (LangChain ≥1.0 / LangGraph API)."""

import json
import logging
import os
import uuid
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.tools import tool as lc_tool

from agentic_memory.distillation.callback_handler import TrajectoryCapture
from agentic_memory.distillation.pipeline import DistillationPipeline
from agentic_memory.retrieval.hybrid_retriever import HybridRetriever
from agentic_memory.retrieval.progressive import format_at_level
from agentic_memory.schema import KeyFile, TaskMemory
from agentic_memory.store.memory_store import MemoryStore

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a memory-augmented code agent. You have access to a knowledge store of past task solutions.

WORKFLOW:
1. ALWAYS call memory_lookup() first with the task and repo_id before any code exploration.
2. If results are returned, call memory_get(id, level="L1") on the top result to see key files.
3. If the memory looks relevant or ambiguous, call memory_get(id, level="L2") to get full solution steps and pitfalls.
   If L1 shows the memory is clearly irrelevant, skip L2.
4. Apply the steps. Verify that key_files still exist and are relevant.
5. After completing the task, call memory_rate() on every memory you used:
   - factual="correct" if the steps worked
   - factual="incorrect" with a note if files moved or steps were wrong
   - factual="partially_correct" if the pattern helped but some facts were stale
   For irrelevant memories, rate only relevance="irrelevant" and leave factual unset/null.
6. If you discovered a new reusable pattern not in the store, call memory_add().

If no memory matches, proceed with standard exploration. The resulting trajectory will be
distilled into a new memory automatically.
"""

_TRACE_DIR = os.getenv("TRACE_DIR", "./data/traces")


# ---------------------------------------------------------------------------
# Tool factories
# ---------------------------------------------------------------------------


def make_memory_tools(store: MemoryStore, retriever: HybridRetriever, pipeline: DistillationPipeline | None = None):
    """Return LangChain tools for the 4 primary memory operations."""

    @lc_tool
    def memory_lookup(task: str, repo_id: str, top_k: int = 5) -> str:
        """Look up task memories before any code exploration. Call this FIRST with the task and repo_id."""
        results = retriever.search(task, repo_id=repo_id, top_k=top_k)
        if not results:
            return "No memories found."
        return json.dumps(
            [format_at_level(r.memory, r.score, level="L0") for r in results], indent=2
        )

    @lc_tool
    def memory_get(memory_id: str, level: str = "L2") -> str:
        """Retrieve full details of a memory by ID. Use level=L1 for key files, level=L2 for complete steps and pitfalls."""
        memory = store.get(memory_id)
        if memory is None:
            return f"Memory {memory_id!r} not found."
        return json.dumps(format_at_level(memory, score=0.0, level=level), indent=2)

    @lc_tool
    def memory_rate(
        memory_id: str,
        factual: str | None = None,
        relevance: str | None = None,
        note: str | None = None,
    ) -> str:
        """Rate a memory after using it. factual: correct|incorrect|partially_correct. Always call this to close the feedback loop."""
        memory = store.get(memory_id)
        if memory is None:
            return f"Memory {memory_id!r} not found."

        delta = 0.0
        if factual == "correct":
            delta = +0.1
            memory.use_count += 1
        elif factual == "incorrect":
            delta = -0.3
            memory.decay_count += 1
            logger.warning("Memory %s flagged incorrect. Note: %s", memory_id, note)
        elif factual == "partially_correct":
            delta = -0.1
            memory.decay_count += 1

        if relevance == "irrelevant":
            logger.info("Irrelevant memory logged for retrieval tuning: %s", memory_id)

        if note:
            memory.description += f" [Note: {note}]"
        store.upsert(memory)
        if delta != 0.0:
            store.update_confidence(memory_id, delta)

        new_conf = max(0.0, min(1.0, memory.confidence + delta))
        return f"Rated. new_confidence={new_conf:.2f}"

    @lc_tool
    def memory_add(
        repo_id: str,
        task_pattern: str,
        description: str,
        key_files: list[str],
        solution_steps: list[str],
        pitfalls: list[str],
        outcome: str = "success",
    ) -> str:
        """Write a new memory when you discover something reusable mid-session."""
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
        if pipeline is not None:
            action, existing_id = pipeline._dedup_check(memory)
            if action == "duplicate":
                store.update_confidence(existing_id, delta=+0.05)
                return f"Duplicate of {existing_id}; reinforced instead of creating a new memory."
            if action == "overlap":
                pipeline._merge(existing_id, memory)
                return f"Overlapping memory merged into {existing_id}."
        store.upsert(memory)
        return f"Memory added: {memory.id}"

    return [memory_lookup, memory_get, memory_rate, memory_add]


def make_code_tools():
    """Stub code exploration tools (read_file, grep_search, list_dir)."""

    @lc_tool
    def read_file(path: str) -> str:
        """Read a file from the repository. Returns first 3000 characters."""
        try:
            with open(path) as f:
                return f.read(3000)
        except FileNotFoundError:
            return f"File not found: {path}"
        except Exception as exc:
            return f"Error reading {path}: {exc}"

    @lc_tool
    def grep_search(query: str) -> str:
        """Search for a pattern in repository Java, XML, and YAML files recursively."""
        import subprocess

        result = subprocess.run(
            [
                "grep",
                "-r",
                "--include=*.java",
                "--include=*.xml",
                "--include=*.yml",
                "-l",
                query,
                ".",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout[:3000] or "No matches found."

    @lc_tool
    def list_dir(path: str = ".") -> str:
        """List directory contents. Defaults to current directory."""
        try:
            entries = sorted(Path(path).iterdir(), key=lambda p: (p.is_file(), p.name))
            return "\n".join(str(e) for e in entries[:50])
        except Exception as exc:
            return f"Error listing {path}: {exc}"

    return [read_file, grep_search, list_dir]


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


def run_agent(
    task: str,
    repo_id: str,
    llm,
    memory_store: MemoryStore | None = None,
    distillation_pipeline: DistillationPipeline | None = None,
    trace_dir: str | Path | None = None,
) -> dict:
    """Run a memory-augmented ReAct agent on a task.

    Captures the trajectory via callback, saves it to disk, and runs
    offline distillation inline after execution.

    Args:
        task:                   Natural language task description.
        repo_id:                Repository identifier.
        llm:                    LangChain LLM for agent reasoning.
        memory_store:           Optional pre-configured MemoryStore.
        distillation_pipeline:  Optional pre-configured DistillationPipeline.
        trace_dir:              Optional directory where raw traces are saved.

    Returns:
        dict with keys: result, trace_id, tool_calls, total_tokens.
    """
    store = memory_store or MemoryStore()
    retriever = HybridRetriever(store)
    pipeline = distillation_pipeline or DistillationPipeline(store, llm)

    trace_id = f"trace-{uuid.uuid4().hex[:8]}"
    capture = TrajectoryCapture(trace_id=trace_id, repo_id=repo_id, task=task)

    all_tools = make_memory_tools(store, retriever, pipeline) + make_code_tools()

    agent = create_agent(
        model=llm,
        tools=all_tools,
        system_prompt=_SYSTEM_PROMPT,
    )

    result = agent.invoke(
        {"messages": [("user", task)]},
        config={"callbacks": [capture]},
    )

    # Extract final answer from the last message in the graph state
    final_answer = ""
    if result and "messages" in result:
        last_msg = result["messages"][-1]
        final_answer = getattr(last_msg, "content", str(last_msg))

    # Save trace
    trace = capture.to_trace()
    trace_root = Path(trace_dir) if trace_dir is not None else Path(_TRACE_DIR)
    trace_path = str(trace_root / f"{trace_id}.json")
    trace_root.mkdir(parents=True, exist_ok=True)
    capture.save(trace_path)
    logger.info("Trace saved to %s", trace_path)

    # Inline distillation
    try:
        pipeline.run(trace)
    except Exception as exc:
        logger.error("Inline distillation failed for %s: %s", trace_id, exc)

    return {
        "result": final_answer,
        "trace_id": trace_id,
        "tool_calls": capture.tool_calls,
        "total_tokens": capture.total_tokens,
    }
