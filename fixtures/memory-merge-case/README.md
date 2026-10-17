# Memory Merge / Accumulation Case

This fixture verifies that repeated related tasks can enrich one reusable memory instead of producing noisy duplicate memories.

The benchmark story:

1. A prior email retry bug produced a memory for transient notification delivery failures.
2. A later SMS retry bug reuses that memory and discovers a new provider-specific pitfall: SMS `429` should retry, SMS `400` should not.
3. A later webhook retry bug reuses the richer memory and adds another pitfall: webhook `503` should retry, webhook `410` should not.
4. The memory should accumulate better steps, anchors, and pitfalls over time.

## Fixture Layout

- `seed-memory/email-retry-policy-memory.json` is the initial memory from an email retry fix.
- `seed-traces/trace-email-retry-policy.json` is the source trace for that memory.
- `1-notification-service-original` shows the source repo shape where the seed memory came from.
- `2-notification-service-test` is the working validation repo.
- `verified-flow.md` records the expected MCP flow.

## Seed the Memory

From the repository root:

```bash
uv run python fixtures/memory-merge-case/seed_memory.py --with-trace
```

With `--with-trace`, the script copies the trace fixture and seeds its
trace-status row as already `processed` for the seeded memory.

Set `MEMORY_DATA_DIR` first if you want to seed a temporary memory store instead of `./data`. Set `TRACE_DIR` if you want `--with-trace` to copy traces somewhere other than `./data/traces`. Set `TRACE_STATUS_DB_PATH` if you want trace status somewhere other than `./data/trace_status.db`.

## Suggested Validation

From `fixtures/memory-merge-case/2-notification-service-test`:

```bash
npm test
```

Before fixes, SMS and webhook retry tests should fail while email tests pass. Run task 01 first, then task 02. After both tasks, all tests should pass and the final memory should be richer than the seed memory.
