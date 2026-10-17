# Verified Flow: Day-2 Production Incident Case

This document describes the intended MCP-backed validation flow for `fixtures/incident-case`.

## Scope

- `seed-memory/payment-captured-incident-memory.json` represents a prior production incident in `payments-api`.
- `1-payments-api-original` shows the source incident shape.
- `2-order-service-test` is the working validation repo.

## Seed Setup

Load the source incident memory into the memory store before the validation run.

From the repository root:

```bash
uv run python fixtures/incident-case/seed_memory.py --with-trace
```

The seed memory says that paid orders stayed `PENDING` because production webhooks used:

- `payment.captured`

while the buggy handler only processed:

- `payment.succeeded`

## Validation Task

Open `2-order-service-test` and ask the agent to complete:

`test-tasks/task-01-payment-webhook-incident.md`

The current repo has a similar incident:

- logs show `payment.captured`
- tests show `order-1001` remains `PENDING`
- `src/handlers/paymentWebhook.js` only handles `payment.succeeded`

## Expected MCP Flow

1. Agent calls `memory_lookup` with a task like "paid orders remain pending after payment webhook".
2. `memory_lookup` returns the prior `payments-api` incident memory through cross-repo fallback.
3. Agent calls `memory_get` to expand the memory.
4. Agent reads `logs/payment-webhook.log`.
5. Agent inspects `src/handlers/paymentWebhook.js` and `src/store/orders.js`.
6. Agent adapts the remembered fix to the current repo.
7. Agent updates the handler so `payment.captured` marks the order `PAID`.
8. Agent preserves duplicate-webhook idempotency.
9. Agent runs `npm test` from `2-order-service-test`.
10. Agent calls:

```text
memory_rate(
  memory_id="<retrieved-memory-id>",
  factual="correct",
  relevance="relevant",
  note="Prior payment.captured incident memory matched the order-service webhook symptom; adapted file path to src/handlers/paymentWebhook.js."
)
```

11. Agent calls `memory_save_trace` so the `order-service` adaptation becomes memory.

## Expected Results

- `payment.captured` should mark the order as `PAID`.
- duplicate captured events should not duplicate status history.
- unrelated events should remain ignored.
- `npm test` should pass after the fix.
- the retrieved incident memory should be reinforced through `memory_rate`.
- the new trace should capture:
  - `logs/payment-webhook.log`
  - `src/handlers/paymentWebhook.js`
  - `payment.captured`
  - idempotent status transition

## What This Proves

This case proves day-2 operational reuse:

- memory can encode incident symptom, logs, root cause, and fix pattern
- future agents can reuse production-debugging knowledge
- cross-repo fallback helps a service with no local incident memory
- the agent still verifies current logs/code before editing
- successful reuse reinforces memory confidence
