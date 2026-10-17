# Auth Service Original

This folder represents the old repo shape where the seed memory was correct.

Auth was header-based:

- `middleware/auth.js` reads `x-user-id`
- `routes/profile.js` reads `req.user.id`

The stale memory in `../seed-memory/stale-auth-middleware-memory.json` was distilled from a successful fix in this version of the service.

## Run

```bash
npm test
```
