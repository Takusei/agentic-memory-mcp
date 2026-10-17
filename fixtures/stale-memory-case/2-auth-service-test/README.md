# Auth Service Test

This folder is the stale-memory validation repo.

The service evolved from header-based auth to session-based auth:

- old path: `middleware/auth.js`
- current path: `middleware/sessionAuth.js`
- old identity: `req.user.id`
- current identity: `req.session.userId`

The validation task should retrieve the old memory, notice that it is partially stale, and fix the current session middleware instead of recreating the old file.

## Run

```bash
npm test
```

The first test is expected to fail before the agent fixes `middleware/sessionAuth.js`.
