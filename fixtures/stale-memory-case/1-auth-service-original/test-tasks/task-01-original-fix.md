# Task 01: Original Auth Profile Fix

Fix the protected profile route so authenticated users can access `/profile`.

Requirements:

- A request with `x-user-id` should return `200`.
- A request without `x-user-id` should return `401`.
- Keep the auth check in `middleware/auth.js`.
- Keep the profile response in `routes/profile.js`.
- Run `npm test`.

Expected memory produced from this old repo:

- Protected profile auth failures usually involve `middleware/auth.js`.
- The legacy identity field is `req.user.id`.
- The legacy auth source is the `x-user-id` header.
