# Plan: Decouple distillation from MCP tool calls

## TL;DR
Today `memory_save_trace` and `memory_rate` both synchronously run the LLM
distillation pipeline. This couples user-facing tool latency to LLM calls and
makes those tools fail/slow whenever the model API is unhappy. Refactor so:

- `memory_save_trace` only persists the trace JSON and records a `pending` row.
- `memory_rate` only updates memory fields (confidence, notes, counts) and, on
  `factual="incorrect"`, flips the source trace's status to `needs_redistill`
  with the note attached.
- A new **background distillation worker** (thread inside the MCP server) polls
  a SQLite-backed trace-status table and processes `pending` + `needs_redistill`
  rows out-of-band.

## Architecture

```
MCP tool calls (fast, no LLM)
  memory_save_trace ──► write trace JSON ──► insert row (status=pending)
  memory_rate       ──► update memory     ──► if incorrect: update row
                                              (status=needs_redistill, note)
                              ▲
                              │ reads/writes
                              ▼
                    ┌────────────────────┐
                    │ TraceStatusStore   │  SQLite: data/trace_status.db
                    │  (id, status,      │
                    │   note, attempts,  │
                    │   last_error,      │
                    │   created_at,      │
                    │   updated_at)      │
                    └────────────────────┘
                              ▲
                              │ polled every N seconds
                              ▼
                    ┌────────────────────┐
                    │  DistillationWorker│  background thread
                    │  - claim pending   │
                    │  - run pipeline    │
                    │  - hybrid merge    │
                    │  - mark processed  │
                    │    or failed       │
                    └────────────────────┘
```

## Phases

### Phase 1 — Trace status store (foundation, no behavior change)
1. Create `src/agentic_memory/store/trace_status_store.py` with a `TraceStatusStore`
   class wrapping a SQLite connection at `data/trace_status.db`.
   - Schema: `traces(trace_id TEXT PRIMARY KEY, status TEXT NOT NULL,
     note TEXT, attempts INTEGER DEFAULT 0, last_error TEXT,
     created_at TEXT, updated_at TEXT)`.
   - Status values: `pending`, `processing`, `processed`, `needs_redistill`,
     `failed`.
   - Methods: `enqueue(trace_id)`, `mark_needs_redistill(trace_id, note)`,
     `claim_next() -> trace_id | None` (atomic update pending→processing),
     `mark_processed(trace_id, memory_id)`, `mark_failed(trace_id, error)`,
     `get(trace_id)`, `list_by_status(status)`.
2. Add settings to `src/agentic_memory/setting.py`:
   - `TRACE_STATUS_DB_PATH` (default `data/trace_status.db`)
   - `WORKER_POLL_INTERVAL_SEC` (default `5`)
   - `WORKER_MAX_ATTEMPTS` (default `3`)
   - `WORKER_ENABLED` (default `True`)
3. Backfill: at server startup, scan `data/traces/*.json` and insert any trace
   missing from the status DB as `processed` (assume historical traces are done).
   This prevents the worker from re-distilling everything on first run.

### Phase 2 — Background worker (parallel to phase 1)
4. Create `src/agentic_memory/distillation/worker.py` containing
   `DistillationWorker(store, retriever, pipeline_factory, status_store)`:
   - `start()`: spawn daemon thread running `_loop()`.
   - `_loop()`: every `WORKER_POLL_INTERVAL_SEC`, call `claim_next()`.
   - `_process(trace_id)`: load trace JSON, on `needs_redistill` append the
     stored note as an `assistant` message, run pipeline, perform the hybrid
     merge (same logic currently inline in `memory_save_trace`), mark
     processed or failed (with `attempts` increment and `last_error`).
   - `stop()`: graceful shutdown via `threading.Event`.
5. Move the **hybrid merge block** out of `memory_save_trace` into a helper
   `_hybrid_merge_after_distill(memory, repo_id)` in the worker module so it
   can be reused.

### Phase 3 — MCP tool refactor (depends on 1 & 2)
6. **`memory_save_trace`**: remove the `pipeline.run(...)` call and the
   hybrid-merge block. After writing the trace JSON, call
   `status_store.enqueue(tid)`. Return `{"ok": True, "trace_id": tid,
   "status": "pending"}`.
7. **`memory_rate`**: remove the entire `if needs_redistillation: ...` block.
   When `factual == "incorrect"`, call
   `status_store.mark_needs_redistill(memory.source_trace_id, note)` instead.
   Return shape unchanged.
8. **Server startup**: instantiate `TraceStatusStore` and `DistillationWorker`
   alongside the existing `store`/`retriever`. Start the worker if
   `WORKER_ENABLED` and `OPENAI_API_KEY` are both set.

### Phase 4 — Tests + verification
9. New `tests/test_trace_status_store.py`: enqueue → claim_next is atomic
   (cannot be claimed twice), mark_processed/mark_failed, attempts increment,
   needs_redistill flow.
10. Update `tests/test_mcp_tools.py`:
    - `memory_save_trace` no longer requires `OPENAI_API_KEY`; returns
      `status="pending"` and inserts a row.
    - `memory_rate(factual="incorrect", note=...)` updates the trace row
      to `needs_redistill` with the note.
11. New `tests/test_distillation_worker.py`: with a mock LLM pipeline,
    enqueue a trace, run one `_process` iteration, assert status →
    `processed` and memory created. Test the `needs_redistill` path
    appends note to messages. Test failure path increments `attempts`
    and stops at `WORKER_MAX_ATTEMPTS`.
12. Smoke test: `uv run python -m agentic_memory.mcp_server.server`,
    call `memory_save_trace` via inspector, verify SQLite row goes
    pending → processing → processed within ~10 sec.

## Relevant files
- `src/agentic_memory/mcp_server/server.py` — strip distillation from
  `memory_save_trace` (lines ~338–435) and re-distill block from
  `memory_rate` (lines ~139–166); add worker startup.
- `src/agentic_memory/distillation/pipeline.py` — unchanged; the worker
  calls `pipeline.run(trace)` as before.
- `src/agentic_memory/store/trace_status_store.py` — **new**.
- `src/agentic_memory/distillation/worker.py` — **new**, owns the
  hybrid-merge helper moved out of server.py.
- `src/agentic_memory/setting.py` — add 4 worker/DB settings.
- `tests/test_trace_status_store.py`, `tests/test_distillation_worker.py`
  — **new**. `tests/test_mcp_tools.py` — update assertions.

## Verification
1. `uv run pytest tests/ -v` — all existing tests pass; new tests pass.
2. Start server: `uv run python -m agentic_memory.mcp_server.server`.
   Call `memory_save_trace` via fastmcp inspector — should return
   immediately (no LLM call in foreground). Watch logs for worker pickup
   within `WORKER_POLL_INTERVAL_SEC`.
3. Call `memory_rate(memory_id, factual="incorrect", note="X")` — verify
   memory row updated synchronously, source trace row marked
   `needs_redistill`, worker re-processes within poll interval, new memory
   appears (or original is merged) and trace marked `processed`.
4. Kill server mid-distillation: on restart, any rows stuck in
   `processing` should be requeued (see Decisions).
5. Backfill check: delete `trace_status.db`, restart server with existing
   traces in `data/traces/`, verify all are marked `processed` (not
   re-distilled).

## Decisions
- **Storage**: SQLite at `data/trace_status.db` (sibling of existing
  `data/chroma/`, `data/memories/`, `data/traces/`). ACID guarantees the
  atomic `claim_next` without extra locking code.
- **Trigger**: background daemon thread inside the MCP server, polling
  every 5 s. No external cron required, no extra process to manage.
- **Re-distillation flow**: `memory_rate(factual="incorrect")` flips the
  source trace's status to `needs_redistill` and stores the note in the
  same row (single column, latest note wins). Worker picks it up next
  cycle. The current behavior — re-distilling the *same* trace with the
  correction note injected — is preserved.
- **Stuck `processing` rows on crash**: on worker startup, reset any
  `processing` rows back to `pending` (or `needs_redistill` if a note is
  present) so they get retried.
- **Concurrency**: single worker thread for now. SQLite handles the
  atomic claim, so scaling to N workers later only requires removing the
  single-thread assumption.
- **Scope excluded**: no external scheduler integration (cron, systemd
  timer), no metrics endpoint, no admin UI. CLI/MCP tool to manually
  trigger or inspect status can be added later if needed.

## Further Considerations
1. **Should `memory_rate` return immediately even when the memory had
   pending distillation work?** Recommended: yes, return the new
   confidence right away; the worker handles re-distillation
   asynchronously. The response can include `"redistill_queued": true`
   so the caller knows.
2. **Should we expose worker status via an MCP tool** (e.g.
   `memory_pipeline_status() -> {pending: N, processing: N, failed: N}`)?
   Nice-to-have for the eval harness; not required for the refactor.
   Recommend deferring unless evaluation tests need it.
3. **Trace deletion policy**: after `processed`, should we keep the JSON
   file forever? Currently we do, and the status row keeps the link.
   Recommend no change — trace files remain useful for re-distillation
   and debugging.
