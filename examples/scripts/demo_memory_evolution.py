"""Demonstrate the self-evolving memory: cold-start vs warm-start.

Run 1 (cold): no prior memories → agent explores from scratch →
              distillation creates a NEW memory.
Run 2 (warm): memory from run 1 exists → retrieval finds it immediately and
              reinforces confidence.

Usage:
    uv run python scripts/demo_memory_evolution.py

The script uses an isolated data directory (examples/data/demo_evolution/) so
it never pollutes the main memory store. Delete that folder to reset.

By default run 2 is a fast retrieval-only warm-start check so the demo finishes
quickly. Set RUN_FULL_WARM_AGENT=1 to run a second full LLM agent invocation.
"""

import logging
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
# Show only our pipeline decisions, not all the HF/httpx noise
logging.getLogger("agentic_memory.distillation.pipeline").setLevel(logging.INFO)
logging.getLogger("examples.agent.memory_agent").setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TASK = "Upgrade Spring Boot from 2.7 to 3.2 in payment-service"
REPO_ID = "payment-service"
FIXTURE_DIR = REPO_ROOT / "examples" / "fixtures" / "payment-service"
DEMO_DATA_DIR = REPO_ROOT / "examples" / "data" / "demo_evolution"
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
RUN_FULL_WARM_AGENT = os.getenv("RUN_FULL_WARM_AGENT") == "1"

if not FIXTURE_DIR.exists():
    print(f"\nERROR: Example fixture not found: {FIXTURE_DIR}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wipe_data():
    """Remove the isolated demo data directory for a clean cold start."""
    if DEMO_DATA_DIR.exists():
        shutil.rmtree(DEMO_DATA_DIR)
    print(f"  Wiped {DEMO_DATA_DIR} for a clean start.\n")


def _snapshot_memories(store) -> dict[str, tuple[float, int, int]]:
    """Return {memory_id: (confidence, use_count, reinforcement_count)}."""
    return {
        m.id: (m.confidence, m.use_count, m.reinforcement_count)
        for m in store.list_all()
    }


def _run(label: str, store) -> dict:
    from examples.agent.memory_agent import run_agent

    print(f"{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")

    result = run_agent(
        task=TASK,
        repo_id=REPO_ID,
        llm=llm,
        memory_store=store,
        trace_dir=DEMO_DATA_DIR / "traces",
    )

    print(f"\n  Tool calls  : {result['tool_calls']}")
    print(f"  Total tokens: {result['total_tokens']}")
    print(f"  Trace ID    : {result['trace_id']}\n")
    return result


def _run_warm_retrieval(store) -> dict:
    from agentic_memory.retrieval.hybrid_retriever import HybridRetriever

    print(f"{'─' * 60}")
    print("  RUN 2 — Warm start (retrieval-only check)")
    print(f"{'─' * 60}")

    retriever = HybridRetriever(store)
    results = retriever.search(TASK, repo_id=REPO_ID, top_k=1)
    if not results:
        print("\n  No memory retrieved. Warm-start check failed.\n")
        return {
            "tool_calls": 1,
            "total_tokens": 0,
            "memory_id": None,
            "retrieval_score": None,
        }

    top = results[0]
    memory = top.memory
    memory.use_count += 1
    memory.reinforcement_count += 1
    store.upsert(memory)
    store.update_confidence(memory.id, delta=+0.1)
    updated = store.get(memory.id)

    print(f"\n  Retrieved : [{memory.id}] {memory.task_pattern}")
    print(f"  Score     : {top.score:.2f}")
    print(f"  Key files : {', '.join(kf.path for kf in memory.key_files[:3])}")
    print(f"  Confidence: {memory.confidence:.2f} -> {updated.confidence:.2f}\n")

    return {
        "tool_calls": 1,
        "total_tokens": 0,
        "memory_id": memory.id,
        "retrieval_score": top.score,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("\nERROR: OPENAI_API_KEY not set. Add it to your .env file.")
    sys.exit(1)

from langchain_openai import ChatOpenAI

from agentic_memory.store.memory_store import MemoryStore

llm = ChatOpenAI(model=MODEL, temperature=0)

os.chdir(FIXTURE_DIR)

print("\n" + "=" * 60)
print("  SELF-EVOLVING MEMORY DEMO")
print("=" * 60 + "\n")

# ── Clean slate ────────────────────────────────────────────────────────────
_wipe_data()

store = MemoryStore(data_dir=str(DEMO_DATA_DIR))

# ── RUN 1: Cold start ──────────────────────────────────────────────────────
before_run1 = _snapshot_memories(store)
result1 = _run("RUN 1 — Cold start (no prior memories)", store)
after_run1 = _snapshot_memories(store)

new_memories = {k: v for k, v in after_run1.items() if k not in before_run1}
print(f"  Memories after run 1: {len(after_run1)}  (new: {len(new_memories)})")
for mid, (conf, use, reinf) in new_memories.items():
    print(
        f"    [{mid}]  confidence={conf:.2f}  use_count={use}  reinforcement_count={reinf}"
    )

# ── RUN 2: Warm start ─────────────────────────────────────────────────────
if RUN_FULL_WARM_AGENT:
    result2 = _run("RUN 2 — Warm start (full agent run)", store)
else:
    result2 = _run_warm_retrieval(store)
after_run2 = _snapshot_memories(store)

print(f"  Memories after run 2: {len(after_run2)}")
for mid, (conf, use, reinf) in after_run2.items():
    was_conf, was_use, was_reinf = before_run1.get(
        mid, after_run1.get(mid, (conf, use, reinf))
    )
    was = after_run1.get(mid)
    if was:
        delta_conf = conf - was[0]
        delta_reinf = reinf - was[2]
        marker = "  ← reinforced" if delta_reinf > 0 else ""
        print(
            f"    [{mid}]  confidence={conf:.2f} ({delta_conf:+.2f}){marker}  reinforcement_count={reinf}"
        )
    else:
        print(f"    [{mid}]  confidence={conf:.2f}  (new in run 2)")

# ── Summary ────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  COMPARISON SUMMARY")
print("=" * 60)
warm_label = "Run 2 (warm)" if RUN_FULL_WARM_AGENT else "Run 2 (retrieval)"
print(f"  {'Metric':<20} {'Run 1 (cold)':>14} {warm_label:>18}")
print(f"  {'─' * 20} {'─' * 14} {'─' * 18}")
print(f"  {'Tool calls':<20} {result1['tool_calls']:>14} {result2['tool_calls']:>18}")
print(f"  {'Total tokens':<20} {result1['total_tokens']:>14} {result2['total_tokens']:>18}")

reduction_calls = result1["tool_calls"] - result2["tool_calls"]
reduction_tokens = result1["total_tokens"] - result2["total_tokens"]
print(f"  {'Reduction':<20} {reduction_calls:>+14} {reduction_tokens:>+14}")
if not RUN_FULL_WARM_AGENT:
    print("\n  Note: warm run is retrieval-only by default for a fast demo.")
    print("  Set RUN_FULL_WARM_AGENT=1 to run the second full LLM agent invocation.")

if new_memories:
    mid = next(iter(new_memories))
    final = after_run2.get(mid)
    initial = new_memories[mid]
    if final:
        print(f"\n  Memory [{mid}]:")
        print(
            f"    confidence:          {initial[0]:.2f} → {final[0]:.2f}  ({final[0] - initial[0]:+.2f})"
        )
        print(f"    reinforcement_count: {initial[2]} → {final[2]}")
print()
