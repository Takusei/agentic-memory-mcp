# Nuxt2 Simple Migration Case

This is the **Run 3** repository for the agentic-memory evaluation.

Use it after your agent has already completed the complex Nuxt2 → Nuxt3 migration case and created memory.

## Goal

Test whether the agent retrieves and reuses prior Nuxt migration memory instead of re-exploring everything from scratch.

## Why this repo is simpler

It contains fewer files, but intentionally repeats the same migration-relevant patterns:

- `nuxt.config.js` with Nuxt2 `plugins`, `modules`, `router.middleware`, `publicRuntimeConfig`
- Vue 2 global filter in `plugins/filters.js`
- Injected plugin API via `inject('api', ...)`
- Vuex store in `store/auth.js`
- Route middleware in `middleware/auth.js` and `middleware/tracking.js`
- `asyncData` usage in pages
- Dynamic route file: `pages/items/_id.vue`

## Recommended command

Give the agent this task:

```text
Migrate this Nuxt2 application to Nuxt3. Use any relevant prior migration memory if available. Keep the same behavior: item list, item detail page, profile auth guard, price formatting, and tracking middleware.
```

## Evaluation

Compare this run against the first complex migration run:

- Was memory retrieved?
- How many tool calls were used before the agent identified the migration strategy?
- How many files were read?
- Did the agent avoid rediscovering known Nuxt2 → Nuxt3 pitfalls?
- Did final build/dev startup pass?

The expected behavior is not necessarily zero exploration. The agent should still verify local files, but it should start with a better plan because of previous memory.
