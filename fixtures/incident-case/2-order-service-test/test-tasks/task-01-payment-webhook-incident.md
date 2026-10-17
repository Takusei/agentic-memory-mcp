# Task 01: Day-2 Payment Webhook Incident

Production incident:

- Customers are charged successfully.
- Payment webhook delivery is logged as successful.
- Affected orders remain `PENDING`.

Requirements:

- Use any relevant prior incident memory if available.
- Start by reading `logs/payment-webhook.log`.
- Diagnose the mismatch between production event names and the webhook handler.
- Fix the current repo, not the seed/source repo.
- Preserve duplicate webhook idempotency.
- Do not make unrelated events mark orders as paid.
- Run `npm test`.
- Rate any useful retrieved memory as correct/relevant.
- Save a trace at the end so the order-service adaptation can become memory.

Evaluation focus:

- Did the agent retrieve the prior `payment.captured` incident memory?
- Did it inspect logs before editing?
- Did it identify that `payment.captured` is ignored by the handler?
- Did it fix `src/handlers/paymentWebhook.js`?
- Did it preserve idempotency and ignored-event behavior?
- Did it call `memory_rate` with `factual="correct"` and `relevance="relevant"`?
- Did it call `memory_save_trace` after tests passed?
