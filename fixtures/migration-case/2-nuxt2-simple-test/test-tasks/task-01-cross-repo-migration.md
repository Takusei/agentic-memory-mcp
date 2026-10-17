# Task: Cross-Repo Nuxt2 to Nuxt3 Migration

Migrate this Nuxt2 application to Nuxt3.

Use any relevant prior migration memory if available.

Keep the same behavior:

- `/` lists items.
- `/items/:id` shows item detail and returns a 404-style error for unknown items.
- `/profile` is protected by auth middleware.
- prices are displayed in Japanese yen format.
- tracking middleware still runs on client-side navigation.

After migration, update dependencies and config as needed. Run build or explain any remaining issue clearly.

Evaluation focus:

- Did the agent retrieve Nuxt2 → Nuxt3 memory created from the complex repo?
- Did it quickly identify repeated patterns: filters, plugins, middleware, Vuex, asyncData, dynamic routes, runtime config?
- Did it reduce exploration compared with the first migration run?
