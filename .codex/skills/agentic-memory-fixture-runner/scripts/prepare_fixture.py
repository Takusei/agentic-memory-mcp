#!/usr/bin/env python3
"""Plan interactive agentic-memory fixture benchmark runs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CaseConfig:
    fixture_dir: str
    label: str
    verified_flows: tuple[str, ...]


CASES: dict[str, CaseConfig] = {
    "stale-memory": CaseConfig(
        fixture_dir="fixtures/stale-memory-case",
        label="Stale / incorrect memory quality control",
        verified_flows=("verified-flow.md", "verified-flow-incorrect.md"),
    ),
    "incident": CaseConfig(
        fixture_dir="fixtures/incident-case",
        label="Day-2 production incident",
        verified_flows=("verified-flow.md",),
    ),
    "memory-merge": CaseConfig(
        fixture_dir="fixtures/memory-merge-case",
        label="Memory merge / accumulation",
        verified_flows=("verified-flow.md",),
    ),
    "migration": CaseConfig(
        fixture_dir="fixtures/migration-case",
        label="Nuxt migration / cross-repo reuse",
        verified_flows=("verified-flow.md",),
    ),
    "synthetic-workflow": CaseConfig(
        fixture_dir="fixtures/synthetic-workflow-case",
        label="Synthetic learned workflow / cross-repo recall",
        verified_flows=("verified-flow.md",),
    ),
}


def display(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "fixtures" / "README.md").is_file():
            return candidate
    raise SystemExit("error: could not find repo root containing fixtures/README.md")


def task_files(folder: Path) -> list[Path]:
    task_root = folder / "test-tasks"
    if not task_root.is_dir():
        return []
    return sorted(task_root.glob("*.md"))


def phase_folders(case_dir: Path, suffix: str) -> list[Path]:
    return sorted(
        folder
        for folder in case_dir.iterdir()
        if folder.is_dir() and folder.name.endswith(suffix)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print an approval-gated plan for fixture benchmark tasks.",
    )
    parser.add_argument(
        "--case",
        choices=["all", *sorted(CASES)],
        default="all",
        help="Fixture case to plan. Defaults to all.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root or any path inside it. Defaults to current directory.",
    )
    return parser.parse_args()


def selected_cases(case: str) -> list[tuple[str, CaseConfig]]:
    if case == "all":
        return [(name, CASES[name]) for name in sorted(CASES)]
    return [(case, CASES[case])]


def print_task_list(root: Path, folders: list[Path], empty: str) -> None:
    printed = False
    for folder in folders:
        tasks = task_files(folder)
        if not tasks:
            continue
        printed = True
        print(f"- folder: {display(root, folder)}")
        for index, task in enumerate(tasks, start=1):
            print(f"  {index}. {display(root, task)}")
    if not printed:
        print(f"- {empty}")


def main() -> int:
    args = parse_args()
    root = find_repo_root(Path(args.repo_root))

    print(f"repo root: {root}")
    print()
    print("Interactive fixture benchmark plan")
    print()
    print("Approval flow for Codex:")
    print("1. Ask which listed fixture case(s) the user wants to run.")
    print("2. Say: I am going to generate memory first from the *-original task folder(s). Ask for approval before starting.")
    print("3. For each original task below, ask before running that single task. After approval, open the task file and complete it in that folder.")
    print("4. When all original tasks for the selected case are done, say: memory is generated. Ask for approval to process the *-test validation case.")
    print("5. For each test task below, ask before running that single task. After approval, open the task file and complete it in that folder.")
    print("6. Compare the final run with the verified-flow file(s).")
    print()

    for case_name, config in selected_cases(args.case):
        case_dir = root / config.fixture_dir
        original_folders = phase_folders(case_dir, "-original")
        test_folders = phase_folders(case_dir, "-test")

        print(f"Case: {case_name} - {config.label}")
        print(f"Fixture dir: {display(root, case_dir)}")
        print("Verified flow(s):")
        for flow in config.verified_flows:
            print(f"- {display(root, case_dir / flow)}")
        print()
        print("Phase 1 - memory generation tasks from *-original folders:")
        print_task_list(root, original_folders, "no *-original task files found")
        print()
        print("Phase 2 - validation tasks from *-test folders:")
        print_task_list(root, test_folders, "no *-test task files found")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
