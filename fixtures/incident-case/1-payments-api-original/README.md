# Payments API Original Incident

This folder shows the source repo shape that produced the incident memory.

The incident pattern:

- production logs showed `payment.captured`
- the webhook handler originally only processed `payment.succeeded`
- orders stayed `PENDING` even though payment delivery succeeded
- the fix mapped `payment.captured` to the paid transition and preserved duplicate-webhook idempotency

## Run

```bash
npm test
```
