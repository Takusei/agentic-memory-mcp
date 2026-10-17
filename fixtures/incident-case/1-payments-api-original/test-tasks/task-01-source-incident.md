# Task 01: Source Payment Webhook Incident

Investigate a production incident where paid orders remain `PENDING` after webhook delivery.

Requirements:

- Start from `logs/payment-webhook.log`.
- Identify the webhook event type associated with the stuck order.
- Fix `src/handlers/paymentWebhook.js`.
- Preserve duplicate webhook idempotency.
- Run `npm test`.

Expected memory:

- logs are the strongest clue
- `payment.captured` should trigger the paid-order transition
- duplicate captured events should not duplicate paid history
