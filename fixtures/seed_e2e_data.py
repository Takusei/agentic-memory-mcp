#!/usr/bin/env python3
"""Seed neutral E2E runtime data into the data directory.

This prepares an empty `data/` directory with all storage surfaces the MCP
server expects while avoiding benchmark-specific memories. The generated dummy
memories intentionally use unrelated domains and low confidence so fixture task
lookups should not match them.

Generated surfaces:

- memory JSON files under `data/memories/`
- BM25 and Chroma lookup indexes
- trace JSON files under `data/traces/`
- processed trace-status rows in `data/trace_status.db`
- a small `data/e2e_seed_manifest.json` summary
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentic_memory.schema import KeyFile, TaskMemory  # noqa: E402
from agentic_memory.store.memory_store import MemoryStore  # noqa: E402
from agentic_memory.store.trace_status_store import TraceStatusStore  # noqa: E402


@dataclass(frozen=True)
class DummySeed:
    memory_id: str
    trace_id: str
    repo_id: str
    task_pattern: str
    description: str
    key_files: tuple[str, ...]
    solution_steps: tuple[str, ...]
    pitfalls: tuple[str, ...]
    task: str
    final: str


DUMMY_SEEDS = [
    DummySeed(
        memory_id="mem-dummy-recipe-notes-001",
        trace_id="trace-dummy-recipe-notes",
        repo_id="recipe-notes-demo",
        task_pattern="Recipe note formatting cleanup",
        description="Normalize markdown headings in a personal recipe notes demo.",
        key_files=("notes/soups.md", "notes/desserts.md"),
        solution_steps=(
            "Read the note files that contain inconsistent heading levels.",
            "Promote recipe names to level-two headings.",
            "Keep ingredient bullets and preparation paragraphs unchanged.",
        ),
        pitfalls=(
            "Do not rewrite ingredient quantities while changing heading style.",
            "Do not sort recipes because the author keeps a seasonal order.",
        ),
        task="Clean up heading formatting in recipe notes.",
        final="Updated recipe note heading levels without changing recipe content.",
    ),
    DummySeed(
        memory_id="mem-dummy-garden-calendar-001",
        trace_id="trace-dummy-garden-calendar",
        repo_id="garden-calendar-demo",
        task_pattern="Garden calendar label adjustment",
        description="Rename display labels for a small garden planning calendar.",
        key_files=("calendar/spring.json", "calendar/labels.js"),
        solution_steps=(
            "Inspect the label map used by the calendar renderer.",
            "Rename the visible season labels only.",
            "Run the lightweight label snapshot check.",
        ),
        pitfalls=(
            "Do not change the month keys because they are used as stable IDs.",
            "Avoid editing generated calendar export files.",
        ),
        task="Adjust garden calendar labels for readability.",
        final="Changed only user-facing garden calendar labels.",
    ),
    DummySeed(
        memory_id="mem-dummy-book-shelf-001",
        trace_id="trace-dummy-book-shelf",
        repo_id="book-shelf-demo",
        task_pattern="Book shelf sort preference tweak",
        description="Update a demo bookshelf page to prefer title sorting.",
        key_files=("src/books.js", "src/sortPreferences.js"),
        solution_steps=(
            "Find the default sort preference constant.",
            "Switch the default display order from added date to title.",
            "Verify that manual sort overrides still take precedence.",
        ),
        pitfalls=(
            "Do not mutate the sample book fixture order in place.",
            "Keep author grouping disabled unless explicitly requested.",
        ),
        task="Change default bookshelf sorting to title order.",
        final="Set the bookshelf default sort preference to title.",
    ),
    DummySeed(
        memory_id="mem-dummy-color-swatches-001",
        trace_id="trace-dummy-color-swatches",
        repo_id="color-swatches-demo",
        task_pattern="Color swatch caption refresh",
        description="Refresh captions in a static color swatch gallery demo.",
        key_files=("gallery/swatches.json", "gallery/renderCaptions.js"),
        solution_steps=(
            "Inspect static swatch metadata.",
            "Rewrite only caption strings that are shown below swatches.",
            "Confirm hex values and palette IDs remain unchanged.",
        ),
        pitfalls=(
            "Never alter color hex codes while changing captions.",
            "Do not remove archived palettes from the gallery data.",
        ),
        task="Refresh captions in a color swatch gallery.",
        final="Updated swatch captions while preserving palette identifiers.",
    ),
]


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def make_memory(seed: DummySeed, confidence: float) -> TaskMemory:
    now = datetime.now(timezone.utc).isoformat()
    return TaskMemory(
        id=seed.memory_id,
        repo_id=seed.repo_id,
        task_pattern=seed.task_pattern,
        description=seed.description,
        key_files=[KeyFile(path=path) for path in seed.key_files],
        solution_steps=list(seed.solution_steps),
        pitfalls=list(seed.pitfalls),
        outcome="success",
        lexical_anchors=[],
        confidence=confidence,
        source_trace_id=seed.trace_id,
        created_at=now,
        updated_at=now,
    )


def make_trace(seed: DummySeed) -> dict:
    return {
        "trace_id": seed.trace_id,
        "repo_id": seed.repo_id,
        "task": seed.task,
        "messages": [
            {
                "role": "assistant",
                "content": f"I will inspect the small demo repo for: {seed.task}",
            },
            {
                "role": "tool",
                "content": "read_file(" + seed.key_files[0] + ")",
            },
            {
                "role": "result",
                "content": "Found a harmless demo fixture unrelated to benchmark services.",
            },
            {
                "role": "final",
                "content": seed.final,
            },
        ],
        "tool_calls": 1,
        "total_tokens": 220,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed neutral E2E runtime data that should not match fixture tasks.",
    )
    parser.add_argument(
        "--data-dir",
        default="./data",
        help="Runtime data directory to populate. Defaults to ./data.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the target data directory before seeding.",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.05,
        help=(
            "Confidence for dummy memories. Defaults to 0.05, below the "
            "default retrieval threshold so benchmark lookups do not return them."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned seed actions without writing files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not 0.0 <= args.confidence <= 1.0:
        print("error: --confidence must be between 0.0 and 1.0", file=sys.stderr)
        return 2

    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = (ROOT / data_dir).resolve()

    print(f"data dir: {data_dir}")
    print(f"dummy confidence: {args.confidence}")
    for seed in DUMMY_SEEDS:
        print(f"dummy memory: {seed.memory_id} repo_id={seed.repo_id}")
        print(f"dummy trace:  {seed.trace_id}")

    if args.dry_run:
        return 0

    if args.reset and data_dir.exists():
        shutil.rmtree(data_dir)

    trace_dir = data_dir / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)

    store = MemoryStore(data_dir=str(data_dir))
    status_store = TraceStatusStore(str(data_dir / "trace_status.db"))
    manifest: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(data_dir),
        "dummy_confidence": args.confidence,
        "purpose": (
            "Neutral non-benchmark data for exercising memory/traces/index/status "
            "storage without matching fixture task lookups."
        ),
        "memories": [],
        "traces": [],
    }

    try:
        for seed in DUMMY_SEEDS:
            memory = make_memory(seed, confidence=args.confidence)
            store.upsert(memory)
            manifest["memories"].append(
                {
                    "id": memory.id,
                    "repo_id": memory.repo_id,
                    "source_trace_id": memory.source_trace_id,
                    "confidence": memory.confidence,
                }
            )
            print(f"Seeded dummy memory {memory.id} for repo_id={memory.repo_id}")

            trace = make_trace(seed)
            destination = trace_dir / f"{seed.trace_id}.json"
            destination.write_text(json.dumps(trace, indent=2) + "\n")
            status_store.enqueue(seed.trace_id)
            status_store.mark_processed(
                seed.trace_id, memory_id=memory.id, action="created"
            )
            manifest["traces"].append(
                {
                    "trace_id": seed.trace_id,
                    "memory_id": memory.id,
                    "destination": display(destination),
                    "status": "processed",
                    "distill_action": "created",
                }
            )
            print(f"Seeded processed dummy trace {seed.trace_id} -> {memory.id}")
    finally:
        status_store.close()

    archive_dir = data_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = data_dir / "e2e_seed_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote manifest {display(manifest_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
