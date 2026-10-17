# Fixture Benchmark Summary

This folder contains end-to-end benchmark fixtures for the self-evolving agentic memory system. Each case is designed to exercise a different product claim and is paired with a `verified-flow.md`. Historical screenshots and private session logs are not distributed. The walkthroughs describe earlier runs, not a fresh end-to-end validation of this copy.

## Test Case Summary

| Test case | Purpose | Verified flow | Image | Codex CLI log | Copilot log(outdated) |
|---|---|---|---|---|---|
| Synthetic Learned Workflow / Cross-Repo Recall | Proves memory can teach a synthetic workflow name that the model cannot infer without prior knowledge. | [synthetic-workflow-case/verified-flow.md](synthetic-workflow-case/verified-flow.md) | Historical screenshot omitted | Not included in this distribution | - |
| Nuxt Migration / Cross-Repo Reuse | Proves that a capable model can generate reusable migration memory, which a weaker model in a different repo can later retrieve and apply to succeed on a task it could not otherwise complete. | [migration-case/verified-flow.md](migration-case/verified-flow.md) | Historical screenshot omitted | Not included in this distribution | Not included in this distribution |
| Stale / Incorrect Memory Quality Control | Proves that an incorrect memory triggers confidence decay and automatic re-distillation, preventing stale or harmful guidance from persisting across future tasks. | [stale-memory-case/verified-flow.md](stale-memory-case/verified-flow.md), [stale-memory-case/verified-flow-incorrect.md](stale-memory-case/verified-flow-incorrect.md) | Historical screenshot omitted | Not included in this distribution | Not included in this distribution |
| Day-2 Production Incident | Proves memory helps with operational debugging from logs, symptoms, root cause, and cross-repo incident reuse. | [incident-case/verified-flow.md](incident-case/verified-flow.md) | Historical screenshot omitted | Not included in this distribution | Not included in this distribution |
| Memory Merge / Accumulation | Proves that repeated related tasks accumulate into a single enriched memory via merge, with confidence reinforced on each reuse, instead of creating noisy duplicate records. | [memory-merge-case/verified-flow.md](memory-merge-case/verified-flow.md) | Historical screenshot omitted | Not included in this distribution | Not included in this distribution |

## Manual Fixture Test Steps

Use one of the two methods below when re-running a fixture case from a clean state.

### Method 1: Skill-Based Auto Test

1. Delete the repository-level `data/` folder if you want to ignore existing memories and traces from previous runs.

2. Seed neutral E2E runtime data from the repository root before starting Codex. This populates memory JSON files, BM25/Chroma lookup indexes, dummy traces, and processed trace-status rows under `data/` without reusing benchmark case memories:

```bash
uv run python fixtures/seed_e2e_data.py --reset
```

The generated dummy memories use unrelated demo domains and low confidence by default, so fixture task lookups should not match them.

Run a case-specific seed command only when the test intentionally needs that case's real memory:

```bash
uv run python fixtures/stale-memory-case/seed_memory.py
uv run python fixtures/stale-memory-case/seed_memory.py --variant incorrect --with-trace
uv run python fixtures/incident-case/seed_memory.py --with-trace
uv run python fixtures/memory-merge-case/seed_memory.py --with-trace
```

3. Start Codex in a terminal, in agent chat, run the fixture skill with your target case, for example:

```text
› $agentic-memory-fixture-runner I wanna test incident-case
```

4. Compare the completed run against the case's `verified-flow.md`. Confirm the expected code changes, memory tool behavior, memory ratings, saved trace, and local test results all match the documented expected results.

### Method 2: Manual Test

1. Delete the repository-level `data/` folder if you want to ignore existing memories and traces from previous runs.

2. Seed neutral E2E runtime data from the repository root:

```bash
uv run python fixtures/seed_e2e_data.py --reset
```

Run a case-specific seed command only when needed:

```bash
uv run python fixtures/stale-memory-case/seed_memory.py
uv run python fixtures/stale-memory-case/seed_memory.py --variant incorrect --with-trace
uv run python fixtures/incident-case/seed_memory.py --with-trace
uv run python fixtures/memory-merge-case/seed_memory.py --with-trace
```

3. Start Codex in a terminal, run `/ide`, and confirm IDE mode is enabled.

4. In the IDE, open the target `*-test` folder for the case, then open the relevant file under `test-tasks/`, such as `test-tasks/task-01-stale-memory-validation.md`.

5. Ask Codex to perform the task from that file, for example:

```text
do this task for me
```

6. Compare the completed run against the case's `verified-flow.md`. Confirm the expected code changes, memory tool behavior, memory ratings, saved trace, and local test results all match the documented expected results.

## Benchmark Matrix

| Test case | Task shape | Memory behavior exercised | Observed result from Copilot run | What it proves |
|---|---|---|---|---|
| Synthetic Learned Workflow / Cross-Repo Recall | A source repo defines `GLASS_TULIP_ARCHIVE_V1`; a later repo asks for that workflow by name only. | `memory_lookup`, `memory_get` (L1/L2), `memory_rate(factual="correct")`, `memory_save_trace`; second-phase agent retrieves the synthetic workflow and applies hidden file movement/reporting rules. | Original task saved trace `b1908b2d-a256-4701-a07e-4ba8d072420d`, which distilled into cross-repo memory `mem-9975bc13`. A cold constrained retry without MCP memory correctly reported that it did not know the workflow. With memory enabled, validation retrieved `mem-9975bc13`, applied the workflow, passed `npm test` (3/3), rated the memory correct/relevant (confidence 0.8→0.9), and saved trace `0b96adbc-a5dd-4486-ad92-18e5d95dee12`, which merged back into the same memory. | Memory can encode and replay an arbitrary workflow name that the model cannot know from pretraining or prompt context, with lower flakiness than a framework migration. |
| Nuxt Migration / Cross-Repo Reuse | Nuxt 2→3 migration in the original fixture (high model), followed by a cross-repo validation using a weaker model. | `memory_lookup`, `memory_get` (L1/L2), `memory_save_trace`, `memory_rate(factual="correct")`; second-phase low model retrieves migration memory to fix a runtime issue it could not diagnose cold. | High model completed the Nuxt 2→3 migration and saved `mem-c34a8d63` (confidence 0.8). Low model in the same repo, without memory, could not fix the Vite-node IPC `EINVAL` dev-server error. Low model with memory retrieved `mem-c34a8d63`, identified the macOS Unix socket path limit root cause, patched `package.json` dev script to use a short `TMPDIR`, and verified `HTTP 200` and a clean production build. Memory rated correct; trace `d497e9a8` distilled as a new `mem-5b25ac0f`. | Memory generated by a capable model can be retrieved by a weaker model in a different session to complete a task it could not solve cold; the low model succeeded only when memory was available. |
| Stale Memory / Partially Correct | Evolved auth service moved from `middleware/auth.js` / `req.user.id` to `middleware/sessionAuth.js` / `req.authenticatedUserId`. | `memory_lookup`, `memory_get` (L1/L2), `memory_rate(factual="partially_correct")`, `memory_save_trace`. | Retrieved `mem-962f140f` (legacy auth pattern) and `mem-incorrect-public-profile-001` (bad public-profile workaround). Used original memory as stale context only: identified the correct files but adapted the field name from `req.user.id` to `req.authenticatedUserId`. Patched `middleware/sessionAuth.js`, ran `npm test` (2/2 passed). `mem-962f140f` rated `partially_correct` (confidence 0.8→0.70); validation trace `a6fb3683` distilled as `merged` back into `mem-962f140f`. | Stale memory is a useful starting hypothesis but must be verified against the current repo. Confidence decays on partial matches while the corrected path is preserved in the merged memory. |
| Stale Memory / Incorrect | Intentionally wrong memory recommends making a protected profile route public. | `memory_lookup`, `memory_get` (L1/L2), `memory_rate(factual="incorrect")`, automatic re-distillation triggered by the incorrect rating. | Retrieved `mem-incorrect-public-profile-001` (bad hotfix: bypass session auth, return demo profile). Agent read L2, identified it as a security regression, and rejected it. Rated `factual="incorrect"`; confidence decayed from 0.62→0.32 and `redistill_queued=true` was returned, triggering automatic re-distillation of the source trace `trace-bad-public-profile-hotfix`. | Incorrect memory is automatically queued for re-distillation when rated; harmful or outdated patterns are corrected at the source rather than only being surfaced and ignored. |
| Day-2 Production Incident | Production logs show `payment.captured`; handler only processes `payment.succeeded`; orders remain `PENDING`. | Cross-repo retrieval, `memory_get`, log-first diagnosis, `memory_rate(factual="correct")`, `memory_save_trace`. | After a redo using memory tools properly, `memory_lookup` surfaced `mem-payment-captured-incident-001`; Copilot read logs, fixed the handler, preserved idempotency, passed all 3 tests, rated memory correct/relevant, and saved a new trace. | Agentic memory can encode incident symptoms and root-cause patterns, not just planned coding tasks. Cross-repo fallback can help a service with no local incident memory. |
| Memory Merge / Accumulation | Notification retry policy evolves from email to SMS to webhook. | `memory_lookup`, `memory_get` (L1/L2), `memory_rate(factual="correct")`, `memory_save_trace`, hybrid merge into existing memory. | Email retry task created `mem-740141d4` (confidence 0.8). SMS retry task created `mem-16b76590` (`distill_action=created`). Webhook retry task retrieved both memories, used them as accumulated context, added `WEBHOOK_503` retry branch, ran `npm test` (7/7 passed), and saved trace `ebdf1763`. That trace processed as `distill_action=merged` into `mem-16b76590`; both email and SMS memories rated `factual="correct"` (confidence 0.9). | Memory accumulates across repeated related tasks: each new task reinforces and merges into the existing record, so confidence and pitfall coverage grow over time rather than spawning separate duplicates. |

## Tool Coverage

| MCP tool | Covered by |
|---|---|
| `memory_lookup` | all benchmark cases |
| `memory_get` | stale-memory, incident, memory-merge, synthetic-workflow |
| `memory_rate` | stale-memory, incident, memory-merge, synthetic-workflow |
| `memory_save_trace` | all benchmark cases |
| `memory_update` | available for explicit manual correction; not the primary path in these flows |
| `memory_delete` | used during memory-merge debugging cleanup; covered directly by unit tests |

## Notes

- The images are included as quick visual evidence for the benchmark cases.
- The Codex CLI and Copilot logs are intentionally included because the project requirement asks for records of agent/vibe-coding conversations across tools.
- Some logs include intermediate failed attempts, such as read-only database errors or initial lookup misses. These are useful evidence: they show operational constraints and how the workflow was corrected.
- `*-test` folders are the runnable validation repos. Run agent tasks and local tests directly in those folders.
- `*-original` folders are historical source/baseline repos and should stay untouched unless a task explicitly targets them.
- Case-specific seeded memories need matching trace fixtures and trace-status rows if `memory_rate(factual="incorrect")` is expected to exercise re-distillation. The neutral `fixtures/seed_e2e_data.py` script seeds dummy trace/status rows for storage coverage; the per-case seed scripts seed real benchmark traces when passed `--with-trace`.
- Benchmark agents should use MCP tools to retrieve memory, not inspect `data/memories` directly.
