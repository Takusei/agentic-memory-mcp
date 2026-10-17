# Order Service Test

This folder is the day-2 production incident validation repo.

The incident:

- `logs/payment-webhook.log` shows successful `payment.captured` delivery.
- `src/handlers/paymentWebhook.js` only handles `payment.succeeded`.
- `npm test` fails because `order-1001` remains `PENDING`.

Use this folder as the working folder for agent runs.
