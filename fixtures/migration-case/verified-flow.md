# Verified Flow: MCP Server Test for Migration Case

This document records the verified flow for the `fixtures/migration-case` benchmark set.

## Scope

- `1-nuxt2-migration-original` is a backup baseline and stays untouched.
- `2-nuxt2-simple-test` is the validation run that reuses migration memory and checks the result.

## What I Tested

I used VS Code with GitHub Copilot to run the MCP-backed workflow described by the repo instructions.

1. Opened the migration-case workspace in VS Code and used the instruction-driven MCP workflow.
2. Used prior migration memory from the complex Nuxt2 migration run.
3. Switched to `2-nuxt2-simple-test` and ran the same migration-style task.
4. Let the instructions workflow retrieve the prior memory automatically and apply it to the validation run.
5. Confirmed the repeated Nuxt patterns were reused instead of rediscovered from scratch.
6. Validated the migrated app with dev startup, route checks, and a production build.

## Expected Results

- Memory from the source run should be available for the validation run.
- The source fixture should create or update entries in `data/memories`.
- The validation fixture should reuse the migration pattern from folder 2.
- The app should keep the same behavior after migration:
  - `/` lists items.
  - `/items/:id` shows item detail and returns a 404-style error for unknown items.
  - `/profile` is protected by auth middleware.
  - Prices use Japanese yen formatting.
  - Tracking middleware still runs on client-side navigation.
- The final build should succeed.

## Actual Results

- A prior source run produced reusable migration memory.
- `memory_lookup` and `memory_get` found and loaded that memory for the validation run.
- `memory_save_trace` created a new distilled trace memory.
- `memory_rate` updated confidence for the reused memory.
- The validation run reused the prior Nuxt3 migration patterns directly.
- Dev startup passed.
- Route checks passed for `/`, `/items/1`, `/items/999`, and `/profile`.
- `npm run build` completed successfully.
- The memory store on disk was updated during the save-trace and rate flow.

## What This Proved

- This mainly proves a long trajectory: distilled migration memory created in the complex Nuxt2 repo can be reused in a simpler Nuxt2 repo.
- The MCP server can persist knowledge across related fixture runs.
- The source fixture can accumulate memory through repeated tasks, and the validation fixture can reuse it cross-repo.
- The VS Code + Copilot instruction workflow can retrieve and apply memory automatically.
- This matches the retrieval design because cross-repo fallback exists when repo-scoped results are sparse.
- The `data/memories` store is part of the observable workflow, not just an internal implementation detail.
- The benchmark setup can separate a source case from a validation case while leaving backup folders untouched.

## Short Summary

`2-nuxt2-simple-test` proves that prior migration memory can be reused and the migrated app still passes the required behavior checks.
