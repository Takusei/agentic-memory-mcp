# Task 02: Webhook Retry Accumulation

Fix webhook notification retry behavior after the SMS retry fix.

Current failure:

- Webhook provider `503` should retry.
- Webhook provider `410` should not retry.
- Email and SMS retry behavior must stay correct.

Requirements:

- Use any relevant prior retry-policy memory if available.
- Keep retry decisions centralized in `src/retryPolicy.js`.
- Add webhook retry behavior only where appropriate.
- Do not make every webhook error retryable.
- Preserve capped exponential backoff.
- Run `npm test`.
- Rate useful retrieved memory as correct/relevant.
- Save a trace at the end so the retry-policy memory can accumulate webhook-specific knowledge.

Evaluation focus:

- Did the agent retrieve the enriched retry-policy memory?
- Did it add webhook `503` as retryable?
- Did it keep webhook `410` non-retryable?
- Did it preserve email and SMS behavior?
- Did it call `memory_save_trace` after tests passed?
