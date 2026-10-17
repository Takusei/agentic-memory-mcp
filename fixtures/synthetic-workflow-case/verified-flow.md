# Verified Flow: Synthetic Learned Workflow / Cross-Repo Recall Case

This document describes the intended MCP-backed validation flow for `fixtures/synthetic-workflow-case`.

## Scope

- `1-glass-tulip-original` defines the artificial workflow `GLASS_TULIP_ARCHIVE_V1`.
- `2-glass-tulip-test` asks for that workflow by name only.
- The workflow name is intentionally synthetic, so a model should not know the steps without retrieved memory or source-task context.

## Task 01: Learn GLASS_TULIP_ARCHIVE_V1

Open `1-glass-tulip-original` and ask the agent to complete:

`test-tasks/task-01-learn-glass-tulip.md`

Expected flow:

1. Agent reads the task definition for `GLASS_TULIP_ARCHIVE_V1`.
2. Agent moves normal card files from `incoming/cards/` to `archive/cards/`.
3. Agent renames archived card files using each card's internal `id`.
4. Agent moves flagged card files to `archive/quarantine/`.
5. Agent deletes scratch files.
6. Agent reads `analysis/source.json`.
7. Agent writes `reports/glass-tulip-summary.json`.
8. Agent writes the original-only `reports/glass-tulip-audit.md`.
9. Agent runs `npm test`.
10. Agent saves a trace so the workflow can be reused.

Expected memory effect:

- A memory should be created or updated with the workflow name `GLASS_TULIP_ARCHIVE_V1`.
- The memory should include file movement, card ID renaming, scratch cleanup, source analysis, and summary report generation.
- The original-only quarantine/audit branch may be retained as extra context, but the validation repo does not require it.

## Task 02: Apply GLASS_TULIP_ARCHIVE_V1 From Memory

Open `2-glass-tulip-test` and ask the agent to complete:

`test-tasks/task-01-apply-glass-tulip.md`

Expected MCP flow:

1. Agent calls `memory_lookup` for `GLASS_TULIP_ARCHIVE_V1`.
2. Agent retrieves the workflow memory produced by task 01.
3. Agent applies the common workflow subset in the new repo.
4. Agent runs `npm test`.
5. Agent rates the retrieved memory as `factual="correct"` and `relevance="relevant"`.
6. Agent saves a validation trace.

## Expected Results

- `incoming/cards/` contains no card files after the workflow.
- Normal cards are archived under filenames derived from internal card IDs.
- Scratch files are deleted.
- `reports/glass-tulip-summary.json` contains deterministic source counts and card IDs.
- `reports/glass-tulip-audit.md` exists only in the original fixture.
- `npm test` passes in both repos after their respective tasks.

## What This Proves

This case proves simple cross-repo recall of a synthetic workflow:

- the validation prompt does not reveal the workflow steps
- prior memory is necessary to know what `GLASS_TULIP_ARCHIVE_V1` means
- the benchmark is smaller and less flaky than a framework migration
- a lower-capability model can succeed if memory supplies the missing procedure
