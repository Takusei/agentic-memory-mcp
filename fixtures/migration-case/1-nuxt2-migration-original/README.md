# Nuxt2 -> Nuxt3 Agentic Memory Test Case

This repository is a deliberately small but migration-rich Nuxt2 application. It is designed for evaluating a self-evolving agentic memory system.

The benchmark idea is:

1. Let an agent solve a long-running Nuxt2 -> Nuxt3 migration task.
2. Store the agent trajectory.
3. Distill the trajectory into memory.
4. Run follow-up tasks and check whether memory reduces exploration.

## Why this repo is useful

The app contains several Nuxt2/Vue2 patterns that should produce useful migration knowledge:

- `nuxt.config.js` with `target`, `buildModules`, `modules`, `router.middleware`, `serverMiddleware`, `env`, and `build.extend`
- Vue2 global filters in `plugins/filters.js`
- injected plugin API via `inject('api', api)`
- client-only plugin with `mode: 'client'`
- Vuex store modules and `nuxtServerInit`
- route middleware using Nuxt2 context
- pages using `asyncData`, legacy `fetch`, `validate`, dynamic route `_id.vue`
- server middleware using Express/CommonJS
- components using Options API and filters

## Main benchmark task

Ask the agent:

> Migrate this Nuxt2 application to Nuxt3. Keep equivalent behavior where reasonable. Update config, routing, plugins, store/state handling, API server route, data fetching, and Vue filter usage. Record all important migration decisions.

## Expected useful memories

A successful run should produce memory similar to:

- Nuxt2 `nuxt.config.js` maps to Nuxt3 `nuxt.config.ts`; `target` removed; `buildModules` merged into `modules`; `env` should move to `runtimeConfig`.
- Nuxt2 `serverMiddleware` should migrate to Nitro server routes under `server/api`.
- Nuxt2 global Vue filters are removed in Vue3; replace with utility functions or computed formatting.
- Nuxt2 `plugins/*.js` using `inject` should migrate to `defineNuxtPlugin` and `nuxtApp.provide`.
- Nuxt2 `_id.vue` dynamic routes become `[id].vue`.
- Vuex is not the default in Nuxt3; use Pinia or `useState` for small state.
- `asyncData`/legacy `fetch` should migrate to `useAsyncData`/`useFetch` in `<script setup>`.
- Route middleware should migrate to `defineNuxtRouteMiddleware`.

## Follow-up benchmark tasks

After the migration memory is created, run these tasks and compare with/without memory:

1. Add a wishlist feature using the same state-management pattern chosen during migration.
2. Fix product detail page loading when the product ID is invalid.
3. Add a new server API endpoint `/api/orders` and consume it from a page.
4. Refactor product price formatting across the app.
5. Add auth protection to another page using the migrated middleware pattern.

## Suggested metrics

Capture these before and after memory retrieval:

- total tool calls
- file reads
- grep/search calls
- token usage
- wall-clock time
- task success rate
- number of failed attempts/backtracks
- whether retrieved memory was rated relevant/correct

## Ground-truth migration hotspots

See `expected-memory/nuxt2-to-nuxt3-memory.json` for the kind of memory this repo is expected to generate.
