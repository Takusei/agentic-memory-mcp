## Requirements

### Q1. Design a suite of Cases that can be used to show case the effects of the self-evolving Agentic Memory, this suite of cases will also be used to measure and evaluate the system to be developed.

**Answer:**

See [`fixtures/README.md`](fixtures/README.md) for the full benchmark suite,
verified flows, screenshots, and agent run logs.

In short, the suite contains five main cases:

- **Synthetic workflow case / cross-repo recall**: proves that memory can teach
  an arbitrary workflow name that the model cannot
  infer from general knowledge or the validation prompt alone.
- **Migration case / cross-repo reuse**: proves that a memory distilled from a
  successful high-capability agent run can later help a weaker agent solve a
  similar task in another repo/session.
- **Incident case**: proves that memory can encode Day-2 debugging knowledge,
  including symptoms, logs, root cause, and remediation steps.
- **Stale / incorrect memory case**: proves that agents must verify retrieved
  memory against the current repo, decay partially correct memory, reject
  incorrect memory, and trigger re-distillation when memory is harmful.
- **Memory merge case**: proves that related task memories can accumulate into
  a stronger merged memory instead of creating noisy duplicates.

These fixtures are used both as demonstrations and as an evaluation matrix for
memory lookup, progressive disclosure, rating, trace saving, redistillation,
and merge behavior.

### Q2. Clear requirement, arch/design, planning documents with human approval.

**Answer:**

The original requirements and design notes are preserved under `.docs/`.

- [`SPEC.md`](.docs/SPEC.md): initial project specification and architecture.
- [`DECOUPLE_SPEC.md`](.docs/DECOUPLE_SPEC.md): design plan for decoupling
  trace saving from synchronous LLM distillation.

We don't design every detail in the beginning, the design evolved during implementation and testing.
Here are the final architecture and roadmap for next phases.

- [`ROADMAP.md`](ROADMAP.md): current Phase II / Phase III roadmap.
- [`README.md`](README.md): final architecture overview and current system
  behavior.


### Q3. The implementations below in the email is just a reference, the implementation from candidate is not limited to the design below.

**Answer:**

The implementation is not limited to the reference design. The current system is
documented in [`src/README.md`](src/README.md), with the main package under
[`src/agentic_memory`](src/agentic_memory).

The implemented design includes:

- FastMCP server tools for lookup, get, rate, trace save, trace status, worker
  status, and manual memory CRUD.
- Local `TaskMemory` storage with BM25 and Chroma vector indexes.
- Hybrid retrieval using BM25 + vector search, RRF fusion, and reranking.
- L0/L1/L2 progressive disclosure.
- Async trace distillation worker.
- Deduplication and merge pipeline.
- Feedback loop through `memory_rate`.
- Conservative forgetting/archive behavior.

### Q4. Record of vibe coding conversations

**Answer:**

Archived development conversations are not included in this distribution.
See [the design notes](.docs/README.md), fixture walkthroughs, and tests for
architecture and validation details.

## Bonus

### B1. Consideration of day 2 operations e.g. Customer Support, System continuous improvement Feedback Loop, How to make sure following changes will not cause quality degrading ...

**Answer:**

My understanding is that Day 2 operation means we need observability, feedback loop, and regression control.

First, we should monitor logs and traces so we can understand why the agent made a certain decision, such as which memory was retrieved and what context was used.

Second, we should collect user feedback, like whether the user agrees with the answer or whether the answer was actually useful.

Third, we should run benchmarks automatically before releasing changes. If benchmark results drop significantly, we block the change or rollback to the previous stable version, including code, prompt, retrieval logic, or memory snapshot.

This is important because in agentic memory systems, the system may still return an answer, but the quality can silently degrade because of wrong memory, outdated memory, or poor retrieval.

### B2. Roadmap and design of the phase II and phase III of this agentic memory system.

**Answer:**

See [`ROADMAP.md`](ROADMAP.md).

In short:

- **Phase II** focuses on reliability, evaluation, and memory quality:
  benchmark scorecards, trace filtering, multi-turn session grouping, retrieval
  diagnostics, `memory_add` validation, key-file staleness checks, recovery
  tooling, and clearer agent instructions.
- **Phase III** focuses on enterprise readiness and scale: production storage,
  enterprise trace ingestion, observability, RBAC, audit logs, retention,
  privacy/security controls, scalable retrieval tuning, and optional temporal
  or graph memory.

### B3. Comparison of other cutting edge, industry level design for this subject, and your understanding of pros and cons, the evolvement direction of this subject...

**Answer:**

See [`MEMORY_COMPARISON.md`](MEMORY_COMPARISON.md). (Note that some of this comparison is generated with help of Codex)

My short answer is:

- Many industry systems focus on **repository context**, **manual project
  instructions**, **chat/user memory**, **fact memory**, **graph memory**, or
  **skills**.
- This project focuses on **trace-distilled coding experience**: completed
  coding-agent runs are turned into structured `TaskMemory` records containing
  task patterns, key files, solution steps, pitfalls, confidence, and
  provenance.
- The main advantage is that the system learns from previous agent work instead
  of only searching the current repository or remembering user preferences.
- The main risk is memory quality. Bad, stale, or irrelevant memory can degrade
  future agent behavior if retrieval, validation, and feedback are weak.
- The evolution direction is to move from a local proof of concept toward a
  team-level memory layer: better evaluation, staleness detection, trace
  filtering, access control, audit logs, human review, and eventually converting
  repeated successful task patterns into executable skills, codemods, or MCP
  tools.
