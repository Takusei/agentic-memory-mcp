"""Seed day-2 incident memories into a MemoryStore.

Usage from the repository root:

    uv run python fixtures/incident-case/seed_memory.py
    uv run python fixtures/incident-case/seed_memory.py --with-trace

Set MEMORY_DATA_DIR to seed a non-default store.
Set TRACE_DIR to choose where source traces are copied when --with-trace is used.
Set TRACE_STATUS_DB_PATH to choose where trace status is seeded.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from agentic_memory.schema import KeyFile, TaskMemory  # noqa: E402
from agentic_memory.setting import TRACE_STATUS_DB_PATH  # noqa: E402
from agentic_memory.store.memory_store import MemoryStore  # noqa: E402
from agentic_memory.store.trace_status_store import TraceStatusStore  # noqa: E402


MEMORY_FILE = "payment-captured-incident-memory.json"


def _load_memory(memory_path: Path) -> TaskMemory:
    data = json.loads(memory_path.read_text())
    key_files = [KeyFile(**item) for item in data.pop("key_files")]
    memory = TaskMemory(**data)
    memory.key_files = key_files
    return memory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-trace",
        action="store_true",
        help="Also copy the matching source trace fixture into TRACE_DIR or ./data/traces.",
    )
    args = parser.parse_args()

    memory_path = Path(__file__).parent / "seed-memory" / MEMORY_FILE
    memory = _load_memory(memory_path)

    store = MemoryStore()
    store.upsert(memory)
    print(f"Seeded incident memory {memory.id} for repo_id={memory.repo_id}")

    if args.with_trace and memory.source_trace_id:
        trace_filename = f"{memory.source_trace_id}.json"
        source = Path(__file__).parent / "seed-traces" / trace_filename
        if not source.exists():
            print(f"No trace fixture found for {memory.source_trace_id}")
            return
        trace_dir = Path(os.getenv("TRACE_DIR", "./data/traces"))
        trace_dir.mkdir(parents=True, exist_ok=True)
        destination = trace_dir / trace_filename
        shutil.copyfile(source, destination)
        print(f"Copied trace fixture to {destination}")

        status_store = TraceStatusStore(TRACE_STATUS_DB_PATH)
        status_store.enqueue(memory.source_trace_id)
        status_store.mark_processed(memory.source_trace_id, memory_id=memory.id)
        status_store.close()
        print(
            "Marked trace status as processed "
            f"for {memory.source_trace_id} -> {memory.id}"
        )


if __name__ == "__main__":
    main()
