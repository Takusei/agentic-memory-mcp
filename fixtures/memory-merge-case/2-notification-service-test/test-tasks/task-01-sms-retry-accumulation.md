# Task 01: SMS Retry Accumulation

Fix SMS notification retry behavior.

Current failure:

- SMS provider `429` should retry.
- SMS provider `400` should not retry.
- Email retry behavior already works and must stay unchanged.

Requirements:

- Use any relevant prior retry-policy memory if available.
- Keep retry decisions centralized in `src/retryPolicy.js`.
- Add SMS retry behavior only where appropriate.
- Do not make every SMS error retryable.
- Preserve capped exponential backoff.
- Run `node --test tests/emailSmsRetry.test.js`.
- It is acceptable that the full `npm test` still fails before task 02 because webhook retry behavior is intentionally not fixed yet.
- Rate useful retrieved memory as correct/relevant.
- Save a trace at the end so the retry-policy memory can accumulate SMS-specific knowledge.

Evaluation focus:

- Did the agent retrieve the email retry-policy memory?
- Did it reuse the general transient-vs-permanent pattern?
- Did it add SMS `429` as retryable?
- Did it keep SMS `400` non-retryable?
- Did it call `memory_save_trace` after tests passed?
