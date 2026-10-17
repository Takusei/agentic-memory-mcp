# Repository Instructions

Follow the Codex agentic-memory workflow in `.codex/agentic-memory.instructions.md`
only when the user's task is for code or fixtures under `fixtures/`.

For tasks outside `fixtures/`, do not run the agentic-memory workflow unless the
user explicitly asks for it.

Summary:

- Before starting, call `memory_lookup` with the task description and the repo ID.
- Check `memory_worker_status` so backend distillation and forgetting state is
  visible.
- If memories are returned, call `memory_get(..., level="L1")` first to triage (key files
  and step/pitfall counts). Call `memory_get(..., level="L2")` only when L1 is
  relevant or ambiguous enough that actual steps and pitfalls may matter. If L1
  is clearly irrelevant, skip L2.
- While working, track key files, steps, and pitfalls.
- After completing the task, call `memory_save_trace` with a concise summary of
  the work, tool calls, key outputs, and final result. Do not include hidden
  chain-of-thought.
- Check `memory_worker_status` again after saving the trace to confirm it was
  queued for backend distillation and to surface forgetting-worker state.
- Rate any memory used with `memory_rate`. For irrelevant memories, rate only
  `relevance="irrelevant"` and leave `factual` unset/null so factual confidence
  is not changed.
- After rating memories, call `memory_trace_status(trace_id)` to confirm the
  distillation outcome (created / merged / duplicate / failed) and record it in
  the session summary. The worker polls every few seconds, so an immediate check
  normally returns `pending`/`processing` with `distill_action="unknown"` — that
  is expected and confirms the trace was queued. Do not sleep; report whatever
  status is observed.
- If a `memory_rate(factual="incorrect")` call returns `redistill_queued=true`,
  it also returns `redistill_trace_id`. Call
  `memory_trace_status(redistill_trace_id)` to see the re-distillation outcome
  (created / merged / duplicate) and record it in the session summary.
- Exclude `fixtures/**/seed-memory/`, `fixtures/**/seed-traces/`, `data/`, and
  `examples/` / `**/examples/` from broad `rg`, `find`, `ls`, or file-read
  exploration. Open those paths only when the user explicitly asks to inspect
  seed fixtures, runtime memory-store data, or examples.
- At the end of every fixture task, output a **Memory Session Summary** block
  (see `.codex/agentic-memory.instructions.md` Section 5 for the exact format)
  covering: tools called and results, retrieved memory IDs with cross_repo flag
  and factual/relevance ratings, whether redistillation was triggered, final
  worker/queue status, and a one-line **Distillation Outcome Analysis**
  explaining why each saved/redistilled trace ended up
  created / merged / duplicate / failed.

Use the immediate parent folder name under `fixtures/` as `repo_id`.
