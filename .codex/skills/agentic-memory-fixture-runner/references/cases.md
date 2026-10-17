# Fixture Case Map

Use this reference when selecting fixture cases and explaining the two-phase run.

| Case | Fixture dir | Phase 1 memory generation | Phase 2 validation | Verified flow |
|---|---|---|---|---|
| `stale-memory` | `fixtures/stale-memory-case` | `1-auth-service-original/test-tasks` | `2-auth-service-test/test-tasks` | `verified-flow.md`, `verified-flow-incorrect.md` |
| `incident` | `fixtures/incident-case` | `1-payments-api-original/test-tasks` | `2-order-service-test/test-tasks` | `verified-flow.md` |
| `memory-merge` | `fixtures/memory-merge-case` | `1-notification-service-original/test-tasks` | `2-notification-service-test/test-tasks` | `verified-flow.md` |
| `migration` | `fixtures/migration-case` | `1-nuxt2-migration-original/test-tasks` | `2-nuxt2-simple-test/test-tasks` | `verified-flow.md` |
| `synthetic-workflow` | `fixtures/synthetic-workflow-case` | `1-glass-tulip-original/test-tasks` | `2-glass-tulip-test/test-tasks` | `verified-flow.md` |

Run the planner:

```bash
uv run python .codex/skills/agentic-memory-fixture-runner/scripts/prepare_fixture.py --case <case>
```

The planner prints the current task files from disk. Use that output as the source of truth if it differs from this static map.
