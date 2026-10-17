# Day-2 Production Incident Case

This fixture verifies that agentic memory helps with day-2 operational debugging, not only planned migrations.

The benchmark story:

1. A prior incident in `payments-api` found that successful payment webhooks used `payment.captured`, not `payment.succeeded`.
2. The distilled memory captured the symptom, logs, key files, fix steps, and idempotency pitfall.
3. A later incident in `order-service` has the same symptom: paid orders remain `PENDING` after webhook delivery.
4. The agent should retrieve the prior incident memory, use it as diagnosis guidance, inspect the current logs/code, fix the handler, rate the memory as correct/relevant, and save a new trace.

## Fixture Layout

- `seed-memory/payment-captured-incident-memory.json` is prior incident memory from `payments-api`.
- `seed-traces/trace-payment-captured-incident.json` is the source trace for the seed memory.
- `1-payments-api-original` shows the old source incident shape where the memory came from.
- `2-order-service-test` is the working repo for the validation run.
- `verified-flow.md` records the expected end-to-end MCP flow.

## Seed the Memory

From the repository root:

```bash
uv run python fixtures/incident-case/seed_memory.py --with-trace
```

With `--with-trace`, the script copies the trace fixture and seeds its
trace-status row as already `processed` for the seeded memory.

Set `MEMORY_DATA_DIR` first if you want to seed a temporary memory store instead of `./data`. Set `TRACE_DIR` if you want `--with-trace` to copy traces somewhere other than `./data/traces`. Set `TRACE_STATUS_DB_PATH` if you want trace status somewhere other than `./data/trace_status.db`.

## Suggested Validation

From `fixtures/incident-case/2-order-service-test`:

```bash
npm test
```

Before the fix, the captured-payment test should fail because the handler ignores `payment.captured`. After the agent fixes the webhook handler, all tests should pass.
