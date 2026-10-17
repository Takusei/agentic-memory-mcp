# Task 01: Source Email Retry Policy Fix

Fix email notification retry behavior.

Requirements:

- `SMTP_TEMP` should retry.
- `SMTP_PERM` should not retry.
- Keep retry decisions centralized in `src/retryPolicy.js`.
- Preserve capped exponential backoff.
- Run `npm test`.

Expected memory:

- transient provider failures can retry
- permanent provider failures should stop
- retry logic belongs in `src/retryPolicy.js`
