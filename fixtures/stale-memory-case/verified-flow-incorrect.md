# Verified Flow: Incorrect Memory Rejection Case

This document describes the stricter quality-degradation test for `fixtures/stale-memory-case`.

Unlike the partially stale memory flow, this case uses a memory that is actively wrong. The memory recommends making a protected profile route public. A correct agent should reject it, rate it as incorrect, and avoid changing already-correct code.

## Scope

- `seed-memory/incorrect-public-profile-memory.json` is intentionally wrong.
- `2-auth-service-test` is the working validation repo.
- The validation repo should already preserve protected profile behavior:
  - valid `session.userId` returns `200`
  - missing session returns `401`

## Seed Setup

Use a clean memory data directory when possible so the intentionally incorrect memory is the main retrieved candidate.

From the repository root:

```bash
uv run python fixtures/stale-memory-case/seed_memory.py --variant incorrect
```

To exercise the `memory_rate(factual="incorrect")` re-distillation path, seed the
matching trace and trace-status row too:

```bash
uv run python fixtures/stale-memory-case/seed_memory.py --variant incorrect --with-trace
```

The incorrect memory says to:

- bypass `middleware/sessionAuth.js`
- return a demo anonymous profile
- stop preserving missing-session `401`

This advice is wrong for the current service.

## Validation Task

Open `2-auth-service-test` and ask the agent to complete:

`test-tasks/task-02-incorrect-memory-validation.md`

## Expected MCP Flow

1. Agent calls `memory_lookup` with a task like "validate profile route auth regression".
2. `memory_lookup` returns the public-profile workaround memory.
3. Agent calls `memory_get` to inspect it.
4. Agent compares the memory against the current requirements and tests.
5. Agent rejects the recommendation because it would make `/profile` public.
6. Agent runs `npm test` from `2-auth-service-test`.
7. Agent calls:

```text
memory_rate(
  memory_id="<retrieved-memory-id>",
  factual="incorrect",
  relevance="relevant",
  note="Memory recommends bypassing session auth and returning an anonymous profile, which violates the protected profile requirement."
)
```

8. Agent calls `memory_save_trace` documenting that the memory was unsafe.

## Expected Results

- The agent should not modify `routes/profile.js` to return anonymous profile data.
- The agent should not bypass `middleware/sessionAuth.js`.
- `npm test` should pass.
- The incorrect memory confidence should decay more strongly than a partially correct memory.
- The run should document the rejected unsafe memory.
- If `--with-trace` was used and `OPENAI_API_KEY` is configured, `memory_rate(factual="incorrect")` has a matching source trace and processed trace-status row available for re-distillation.

## What This Proves

This case proves the memory system can reject harmful prior knowledge:

- related memories are not automatically trusted
- incorrect memories can be rated with `factual="incorrect"`
- unsafe or obsolete fixes decay faster
- preserving current behavior matters more than maximizing memory reuse
