# Expected Memory Usage

The agent should ideally retrieve a memory similar to:

- Nuxt2 to Nuxt3 migration pattern
- Replace Vue 2 global filters with composables/helpers
- Migrate injected Nuxt2 plugins to Nuxt3 plugins using `defineNuxtPlugin`
- Replace Vuex store usage with Pinia or a composable state pattern
- Migrate `asyncData` usage to Nuxt3 data fetching patterns
- Rename dynamic route files from `_id.vue` to `[id].vue`
- Migrate middleware to Nuxt3 `defineNuxtRouteMiddleware`
- Move config from Nuxt2 `nuxt.config.js` to Nuxt3 `nuxt.config.ts`

For this simple repo, the agent should still inspect the local files, but it should not need to rediscover the migration strategy from scratch.
