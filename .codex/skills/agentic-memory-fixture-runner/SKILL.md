---
name: agentic-memory-fixture-runner
description: Interactive workflow for this repository's agentic-memory benchmark fixtures. Use when the user wants Codex to run fixture E2E cases, choose which fixture case to execute, generate memory from *-original folders first, then run *-test validation tasks, with user approval before each phase and each task.
---

# Agentic Memory Fixture Runner

## Overview

Use this skill to run fixture benchmarks interactively in two approval-gated phases:

1. Generate memory by completing tasks in the selected case's `*-original` folder(s).
2. Process the validation case by completing tasks in the selected case's `*-test` folder(s).

The user must approve the memory-generation phase, the validation phase, and every individual task before Codex runs it.

## Quick Start

From the repository root, inspect the available cases and tasks:

```bash
uv run python .codex/skills/agentic-memory-fixture-runner/scripts/prepare_fixture.py --case all
```

For one case:

```bash
uv run python .codex/skills/agentic-memory-fixture-runner/scripts/prepare_fixture.py --case stale-memory
```

Supported cases: `stale-memory`, `incident`, `memory-merge`, `migration`, `synthetic-workflow`, or `all`.

## Required Interaction

1. Ask the user which fixture case(s) they want to run if they did not specify one.
2. Run the helper with the selected case to list original/test task files.
3. Tell the user: "I am going to generate memory first from the `*-original` task folder(s). Do you approve?"
4. If approved, handle original tasks one by one:
   - Before each task, ask: "Approve running `<task path>` in `<folder>`?"
   - Only after approval, open the task file and perform it in that folder.
   - Follow `.codex/agentic-memory.instructions.md` for fixture tasks.
5. After all original tasks for that case are complete, tell the user: "The memory-generation phase is done. Do you approve processing the `*-test` validation task(s)?"
6. If approved, handle test tasks one by one:
   - Before each task, ask: "Approve running `<task path>` in `<folder>`?"
   - Only after approval, open the task file and perform it in that folder.
   - Follow `.codex/agentic-memory.instructions.md` for fixture tasks.
7. Compare the completed validation run against the case's `verified-flow*.md`.

If the user does not approve a phase or task, stop that phase cleanly and summarize what remains.

## Important Rules

- Do not run all tasks silently.
- Do not skip the `*-original` memory-generation phase unless the user explicitly says memory has already been generated for that case.
- Do not proceed from original tasks to test tasks without asking.
- Do not proceed from one task to the next without asking.
- Do not inspect `data/`, `examples/`, `**/examples/`, `fixtures/**/seed-memory/`, or `fixtures/**/seed-traces/` as service source code.
- Prefer the task files discovered by the helper over hard-coded paths.

## Notes

- The helper is a planner; it does not execute tasks.
- `fixtures/seed_e2e_data.py` creates neutral runtime data only. It is not a substitute for generating benchmark memory from the selected `*-original` tasks.
- If Codex/MCP was already running before new memories were generated, restart Codex before expecting `memory_lookup` to see newly generated indexes consistently.

See `references/cases.md` for the case map and expected phase folders.
