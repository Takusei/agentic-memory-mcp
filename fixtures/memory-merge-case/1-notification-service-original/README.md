# Notification Service Original

This folder shows the source retry-policy task that produced the seed memory.

The original bug family:

- transient email provider errors should retry
- permanent email provider errors should not retry
- retry decisions should stay centralized in `src/retryPolicy.js`

## Run

```bash
npm test
```
