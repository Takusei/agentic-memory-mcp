"""Run the memory-augmented agent on a task.

Usage:
    uv run python scripts/run_agent.py

Requires:
    OPENAI_API_KEY in .env (or environment).

The script seeds demo memories so the agent gets a memory hit on the Spring
Boot migration task, then runs inside examples/fixtures/payment-service/ so the
agent's read_file / list_dir calls resolve against real files.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# ---------------------------------------------------------------------------
# Config — edit these to change what the agent does
# ---------------------------------------------------------------------------

TASK = "Upgrade Spring Boot from 2.7 to 3.2 in payment-service"
REPO_ID = "payment-service"

# Run the agent from inside the example fixture repo so file paths resolve correctly
FIXTURE_DIR = REPO_ROOT / "examples" / "fixtures" / "payment-service"
if not FIXTURE_DIR.exists():
    print(f"\nERROR: Example fixture not found: {FIXTURE_DIR}")
    sys.exit(1)
os.chdir(FIXTURE_DIR)

# LLM model — gpt-4o-mini is cheapest for demos; swap for gpt-4o for better results
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
EXAMPLE_DATA_DIR = REPO_ROOT / "examples" / "data" / "agent"

# ---------------------------------------------------------------------------
# Check API key before mutating the demo memory store
# ---------------------------------------------------------------------------

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("\nERROR: OPENAI_API_KEY not set. Add it to your .env file.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Seed demo memories so the agent gets a memory hit (skip to test cold-start)
# ---------------------------------------------------------------------------

from examples.scripts.seed_demo_memories import seed  # noqa: E402

print("Seeding demo memories ...")
seed(data_dir=str(EXAMPLE_DATA_DIR))

# ---------------------------------------------------------------------------
# Build LLM
# ---------------------------------------------------------------------------

from langchain_openai import ChatOpenAI  # noqa: E402

llm = ChatOpenAI(model=MODEL, temperature=0)

# ---------------------------------------------------------------------------
# Run the agent
# ---------------------------------------------------------------------------

from agentic_memory.store.memory_store import MemoryStore  # noqa: E402
from examples.agent.memory_agent import run_agent  # noqa: E402

print(f"\nRunning agent on task: {TASK!r}")
print(f"Repo: {REPO_ID!r}, Model: {MODEL}\n")

store = MemoryStore(data_dir=str(EXAMPLE_DATA_DIR))

result = run_agent(
    task=TASK,
    repo_id=REPO_ID,
    llm=llm,
    memory_store=store,
    trace_dir=EXAMPLE_DATA_DIR / "traces",
)

# ---------------------------------------------------------------------------
# Print results
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("RESULT")
print("=" * 60)
print(result["result"])
print()
print(f"Trace ID    : {result['trace_id']}")
print(f"Tool calls  : {result['tool_calls']}")
print(f"Total tokens: {result['total_tokens']}")
print(f"Trace saved : {EXAMPLE_DATA_DIR / 'traces' / (result['trace_id'] + '.json')}")
