# Verified Flow: Memory Merge / Accumulation Case

This document describes the intended MCP-backed validation flow for `fixtures/memory-merge-case`.

## Scope

- `seed-memory/email-retry-policy-memory.json` is a basic memory from an email retry bug.
- `1-notification-service-original` shows the source task that produced the seed memory.
- `2-notification-service-test` is the working validation repo.

## Seed Setup

Seed the initial retry-policy memory:

```bash
uv run python fixtures/memory-merge-case/seed_memory.py --with-trace
```

The seed memory knows:

- transient email errors should retry
- permanent email errors should not retry
- retry logic belongs in `src/retryPolicy.js`

It does not yet know:

- SMS `429` is retryable but SMS `400` is not
- webhook `503` is retryable but webhook `410` is not

## Task 01: SMS Retry Accumulation

Open `2-notification-service-test` and ask the agent to complete:

`test-tasks/task-01-sms-retry-accumulation.md`

Expected MCP flow:

1. Agent calls `memory_lookup` for an SMS transient delivery retry failure.
2. Agent retrieves the email retry-policy memory.
3. Agent uses the general retry-policy pattern but verifies SMS-specific status codes.
4. Agent fixes `src/retryPolicy.js` so SMS `429` retries and SMS `400` does not.
5. Agent runs `node --test tests/emailSmsRetry.test.js`.
6. Agent calls `memory_rate(... factual="correct", relevance="relevant")`.
7. Agent calls `memory_save_trace`.

Expected memory effect:

- Either the existing memory is merged/refined, or a closely related memory is produced.
- The new trace should add SMS-specific anchors and pitfalls.

## Task 02: Webhook Retry Accumulation

After task 01 is complete, ask the agent to complete:

`test-tasks/task-02-webhook-retry-accumulation.md`

Expected MCP flow:

1. Agent calls `memory_lookup` for webhook retry behavior.
2. Agent retrieves the now-richer retry memory.
3. Agent fixes `src/retryPolicy.js` so webhook `503` retries and webhook `410` does not.
4. Agent runs `npm test`.
5. Agent calls `memory_rate(... factual="correct", relevance="relevant")`.
6. Agent calls `memory_save_trace`.

Expected final memory effect:

- The final memory should include email, SMS, and webhook retry knowledge.
- It should have more pitfalls/anchors than the seed memory.
- Repeated tasks should reinforce or merge into a coherent retry-policy memory instead of creating unrelated noise.

## Expected Results

- Email retry behavior remains correct.
- SMS `429` retries.
- SMS `400` does not retry.
- Webhook `503` retries.
- Webhook `410` does not retry.
- the focused SMS test passes after task 01.
- `npm test` passes after both tasks.
- The final distilled memory resembles `expected-memory/notification-retry-policy-merged-memory.json`.

## What This Proves

This case proves memory accumulation:

- related tasks can enrich a prior memory
- repeated task classes get more complete over time
- new pitfalls and lexical anchors are preserved
- useful memories are reinforced
- the memory store should evolve, not just append isolated entries
