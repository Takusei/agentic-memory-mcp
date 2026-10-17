# Agentic Memory - Codex Instructions

This workspace uses an agentic memory MCP server that learns from past coding
sessions.

Apply this workflow only when the user's task is for code or fixtures under
`fixtures/`. For tasks outside `fixtures/`, do not run this workflow unless the
user explicitly asks for agentic memory.

Important: when browsing or searching files, exclude these folders because they
contain mock/generated data and are not representative of real service code:

- `fixtures/**/seed-memory/`
- `fixtures/**/seed-traces/`
- `data/`
- `examples/`
- `**/examples/`

Do not include those paths in broad `rg`, `find`, `ls`, or file-read exploration.
For example, prefer `rg --glob '!data/**' --glob '!fixtures/**/seed-memory/**'
--glob '!fixtures/**/seed-traces/**' --glob '!**/examples/**' ...` when searching
the repo. Open files under those paths only when the user explicitly asks to
inspect seed fixtures, runtime memory-store data, or examples.

## Mandatory Workflow

### 1. Before Starting Any Task

Call `memory_worker_status` to confirm the backend distillation worker state is
visible before doing memory work:

```text
memory_worker_status()
```

Call `memory_lookup` with the task description and repo ID to check for prior
solutions:

```text
memory_lookup(task="<what you are about to do>", repo_id="<folder/service name>")
```

If results are returned, use progressive disclosure before writing code:

1. Call `memory_get(memory_id, level="L1")` to triage: check which files are relevant and how many steps/pitfalls exist.
2. If L1 shows the memory is relevant or ambiguous, call `memory_get(memory_id, level="L2")` to read the actual solution steps and pitfalls before writing any code. L1 only returns counts, not the step content.
3. If L1 shows the memory is clearly irrelevant, do not call L2. Mark it irrelevant later with `memory_rate(relevance="irrelevant", factual=null)` so the memory's factual confidence is not changed.

### 2. During The Task

Work normally. Track which files were key, what steps were taken, and any
surprises or pitfalls encountered.

### 3. After Completing The Task

At the end of every fixture task, call `memory_save_trace` so the work is
queued for backend distillation into reusable memory:

```text
memory_save_trace(
  repo_id="<folder/service name>",
  task="<one-sentence description of what was asked>",
  messages=[
    {"role": "assistant", "content": "<concise rationale / plan summary>"},
    {"role": "tool", "content": "<tool calls made, one per entry>"},
    {"role": "result", "content": "<key outputs, truncated when large>"},
    {"role": "final", "content": "<what was concluded or delivered>"}
  ]
)
```

Capture useful rationale and steps, but do not include hidden chain-of-thought.

After saving the trace, call `memory_worker_status` again to confirm the backend
worker is running and to inspect the current queue summary:

```text
memory_worker_status()
```

### 4. Rate Retrieved Memories

If a retrieved memory was used, call `memory_rate` afterwards:

- `factual="correct"` if the steps worked as described.
- `factual="incorrect"` with a `note` if anything was wrong or outdated.
- `factual="partially_correct"` if the task pattern was useful but some facts were stale.

If a retrieved memory did not apply, rate only relevance:

- `relevance="irrelevant"` and `factual=null`.
- Do not set `factual="correct"` or `factual="incorrect"` for irrelevant memories, because the task did not validate whether the memory was true.

After rating, call `memory_trace_status(trace_id)` to check the distillation outcome.
The rating calls provide a natural delay for the background worker.

```text
memory_trace_status("<trace_id from memory_save_trace>")
```

If a `memory_rate(factual="incorrect")` call returns `redistill_queued=true`, it
also returns `redistill_trace_id` (the source trace of the corrected memory).
Call `memory_trace_status(redistill_trace_id)` as well to see whether the
re-distillation produced a `created`, `merged`, or `duplicate` outcome, and
record that in the session summary.
Timing note: the background worker polls every few seconds and distillation
needs an LLM round-trip, so the status is normally `pending` or `processing`
with `distill_action="unknown"` immediately after `memory_save_trace`. That is
the expected interim state and confirms the trace was queued. Do not sleep or
busy-wait. Call `memory_trace_status` once here after rating and report whatever
the final observed `status` and `distill_action` are — a still-queued trace is a
valid outcome to record.

## repo_id Convention

Use the immediate parent folder name of the code modified, for example:

- Working in `fixtures/payment-service/` -> `repo_id = "payment-service"`

## 5. Required Session Summary

After completing all memory tool calls, output a structured session summary so
the results can be analysed. Use this exact format:

```
## Memory Session Summary

### Tools Called
| Tool | Arguments (brief) | Result |
|---|---|---|
| memory_worker_status | — | <worker running / stopped, queue depth> |
| memory_lookup | task="...", repo_id="..." | <N results / no results> |
| memory_get | id=..., level=L1 | <relevant / not relevant> |
| memory_get | id=..., level=L2 | <used / skipped> |
| memory_rate | id=..., factual=... | <ok / error> |
| memory_save_trace | repo_id=..., task="..." | trace_id=... |
| memory_trace_status | trace_id=... | distill_action=created/merged/duplicate/failed |

### Retrieved Memories
| Memory ID | cross_repo | factual rating | relevance rating | Notes |
|---|---|---|---|---|
| <id> | yes/no | correct / incorrect / partially_correct / not rated | relevant / irrelevant / not rated | <brief note> |

### Redistillation Triggered
- <memory_id>: yes / no — reason: <incorrect rating / manual / none>

### Worker Status (final)
- Worker: <running / stopped>
- Queue: <N pending / empty>

### Distillation Outcome Analysis
- Saved trace `<trace_id>`: distill_action=<created/merged/duplicate/failed>.
  Explain why in one line, e.g. "created — task pattern was novel; vector
  similarity to nearest memory stayed below OVERLAP_THRESHOLD (0.75) and the
  hybrid second-pass found no match >= MERGE_THRESHOLD", or "merged into <id> —
  same task_pattern above overlap", or "duplicate of <id> — similarity >=
  DUPLICATE_THRESHOLD (0.92), existing confidence reinforced".
- Redistilled trace `<redistill_trace_id>` (if any): distill_action=<...> —
  one-line reason.
```

Omit rows for tools that were not called. Output this block in plain text at the
end of every fixture task response.
