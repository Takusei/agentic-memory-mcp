# Task 03: Follow-up bug fix after memory creation

Fix product detail behavior when an invalid product ID is opened.

Requirements:

- `/products/abc` should show a 404 or clean error state.
- `/products/999` should show a 404 or clean error state.
- Do not add duplicate API-fetching logic.

Expected memory reuse:

- Dynamic route migration pattern.
- Nuxt3 error handling.
- Server API endpoint structure.
