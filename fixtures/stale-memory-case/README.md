# Stale Memory / Quality Degradation Case

This fixture verifies that agentic memory can handle stale knowledge safely.

The benchmark story:

1. A prior auth bug fix produced useful memory for `middleware/auth.js`.
2. The repo later evolved and moved auth logic to `middleware/sessionAuth.js`.
3. A future agent retrieves the old memory, notices that the remembered file path and user model are stale, rates the memory as partially correct, and saves an improved trace.
4. A stricter variant seeds an actively wrong memory that recommends making `/profile` public; the agent must reject it and rate it as incorrect.

This case is intentionally small. The important behavior is not application size; it is whether the agent uses memory critically instead of blindly applying outdated instructions.

## Fixture Layout

- `seed-memory/stale-auth-middleware-memory.json` is the old memory to seed into the memory store.
- `seed-memory/incorrect-public-profile-memory.json` is an intentionally wrong memory for the incorrect-rating flow.
- `1-auth-service-original` is the old repo shape where that memory was valid.
- `2-auth-service-test` is the working validation repo.
- `2-auth-service-test/test-tasks/task-01-stale-memory-validation.md` is the partially-correct validation task.
- `2-auth-service-test/test-tasks/task-02-incorrect-memory-validation.md` is the incorrect-memory validation task.
- `verified-flow.md` records the partially-correct MCP flow.
- `verified-flow-incorrect.md` records the incorrect-memory MCP flow.

## Expected Memory Behavior

During the validation run, the agent should:

1. Call `memory_lookup` for the auth/session failure.
2. Retrieve the old memory.
3. Notice `middleware/auth.js` no longer exists.
4. Adapt the remembered pattern to `middleware/sessionAuth.js`.
5. Fix the current session-based auth bug.
6. Rate the old memory as `partially_correct`.
7. Save a new trace so the corrected file path and pitfall become future memory.

## Seed the Memory

From the repository root:

```bash
uv run python fixtures/stale-memory-case/seed_memory.py
```

For the incorrect-memory variant:

```bash
uv run python fixtures/stale-memory-case/seed_memory.py --variant incorrect
```

To also copy the matching source trace fixture and seed its trace-status row for
re-distillation:

```bash
uv run python fixtures/stale-memory-case/seed_memory.py --variant incorrect --with-trace
```

To seed both examples:

```bash
uv run python fixtures/stale-memory-case/seed_memory.py --variant all
```

Set `MEMORY_DATA_DIR` first if you want to seed a temporary memory store instead of `./data`. Set `TRACE_DIR` if you want `--with-trace` to copy traces somewhere other than `./data/traces`. Set `TRACE_STATUS_DB_PATH` if you want trace status somewhere other than `./data/trace_status.db`.

## Suggested Validation

From `fixtures/stale-memory-case/2-auth-service-test`:

```bash
npm test
```

For the partially-correct flow, start from the prepared test folder state. For the incorrect-memory flow, the working repo can already be fixed; the goal is to reject a harmful memory and preserve the passing protected-route behavior.
