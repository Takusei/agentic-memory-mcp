# Task 01: Stale Memory Validation

Fix the profile route regression in this evolved auth service.

Current failure:

- `/profile` returns `401` even when the request has a valid session.
- `npm test` currently fails on the valid-session profile test.

Requirements:

- Use any relevant prior memory if available.
- Do not blindly recreate old files from memory.
- A request with `session.userId` should return `200`.
- A request without a session should return `401`.
- Keep the current session-based auth design.
- Run `npm test`.
- If retrieved memory is useful but stale, rate it as partially correct and explain what changed.
- Save a trace at the end so the memory system can learn the corrected path.

Evaluation focus:

- Did the agent retrieve the old profile auth memory?
- Did it notice `middleware/auth.js` no longer exists?
- Did it adapt the old auth concept to `middleware/sessionAuth.js`?
- Did it avoid copying the old `req.user.id` assumption into the new fix?
- Did it call `memory_rate` with `factual="partially_correct"`?
- Did it call `memory_save_trace` after the fixed tests passed?
