# Verified Flow: Stale Memory Quality Degradation Case

This document describes the intended MCP-backed validation flow for `fixtures/stale-memory-case`.

## Scope

- `seed-memory/stale-auth-middleware-memory.json` represents a memory that used to be correct.
- `1-auth-service-original` shows the old repo shape that produced the memory.
- `2-auth-service-test` is the working validation repo. It evolved from header-based auth to session-based auth, so the old memory is relevant but partially stale.

## Seed Setup

Load the seed memory into the memory store before the validation run.

From the repository root:

```bash
uv run python fixtures/stale-memory-case/seed_memory.py
```

The seed memory says the protected profile route should be fixed in:

- `middleware/auth.js`
- `routes/profile.js`

It also says the user identity is available as `req.user.id`.

## Validation Task

Open `2-auth-service-test` and ask the agent to complete:

`test-tasks/task-01-stale-memory-validation.md`

The current repo no longer has `middleware/auth.js`. The auth middleware moved to:

- `middleware/sessionAuth.js`

The current identity model is also different:

- old memory: `req.user.id`
- current repo: `req.session.userId`

## Expected MCP Flow

1. Agent calls `memory_lookup` with a task like "fix profile 401 after valid session login".
2. `memory_lookup` returns the old auth-route memory because the task pattern and symptoms are related.
3. Agent calls `memory_get` to expand the memory.
4. Agent checks the repo and discovers `middleware/auth.js` is missing.
5. Agent uses the old memory only as partial guidance.
6. Agent fixes `middleware/sessionAuth.js` so valid sessions populate `req.authenticatedUserId`.
7. Agent runs `npm test` from `2-auth-service-test`.
8. Agent calls:

```text
memory_rate(
  memory_id="<retrieved-memory-id>",
  factual="partially_correct",
  relevance="relevant",
  note="Auth route pattern was useful, but middleware/auth.js moved to middleware/sessionAuth.js and req.user changed to req.session.userId."
)
```

9. Agent calls `memory_save_trace` with the validation run so the corrected path and pitfall can be distilled.

## Expected Results

- The agent should not recreate `middleware/auth.js`.
- The agent should not blindly copy `req.user.id` logic.
- `npm test` should pass after the fix.
- The old memory confidence should decay through `memory_rate`.
- The new trace should capture the evolved repo state:
  - `middleware/sessionAuth.js`
  - `req.session.userId`
  - `req.authenticatedUserId`
  - stale-memory pitfall

## What This Proves

This case proves the quality-degradation control loop:

- stale memory can still be retrieved
- stale memory is treated as a hypothesis, not ground truth
- partially wrong memories are rated down
- corrected traces feed the memory system
- future agents should receive a better version of the same task knowledge
