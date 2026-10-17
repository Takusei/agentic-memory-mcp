# Comparative Analysis — Agentic Memory Systems

> Research notes for Agentic Memory MCP.  
> Eight systems surveyed and compared against the project's proposed architecture.

---

## Table of Contents

1. [GitHub Copilot Agentic Memory](#1-github-copilot-agentic-memory)
2. [rohitg00/agentmemory](#2-rohitg00agentmemory)
3. [Mem0](#3-mem0)
4. [memU](#4-memu)
5. [Letta (formerly MemGPT)](#5-letta-formerly-memgpt)
6. [Graphiti / Zep](#6-graphiti--zep)
7. [qmd](#7-qmd)
8. [OpenViking](#8-openviking)
9. [Head-to-Head Comparison](#9-head-to-head-comparison)
10. [What to Borrow](#10-what-to-borrow)
11. [What to Skip](#11-what-to-skip)

---

## 1. GitHub Copilot Agentic Memory

**Approach: Agent-initiated, citation-based, just-in-time verification**

Memory schema is intentionally minimal:

```json
{
  "subject": "API version synchronization",
  "fact": "API version must match between client SDK, server routes, and documentation.",
  "citations": ["src/client/sdk/constants.ts:12", "server/routes/api.go:8"],
  "reason": "..."
}
```

**Key design decisions:**
- **No offline curation** — deliberately skipped (too expensive at scale). Instead each memory carries `citations` pointing to exact `file:line` locations.
- **JIT verification at retrieval time** — before using a memory, the agent reads the cited files to confirm the fact is still valid. Self-heals by storing corrected versions if it finds contradictions.
- **Agent-initiated writing** — agents call `store_memory` when they discover something noteworthy. Nothing is captured automatically.
- **Cross-agent sharing** — Copilot code review, coding agent, and CLI all share the same store.

**Reported results:** 7% higher PR merge rates, 2% more positive code review feedback.

**Gap:** Captures what the agent *observed*, not a distilled `(task_pattern, solution_steps, pitfalls)` recipe. No offline curation pipeline. No trajectory-level extraction.

---

## 2. rohitg00/agentmemory

**Approach: Auto-capture via lifecycle hooks, 4-tier consolidation, no external DBs**

**Memory capture pipeline:**
```
PostToolUse hook fires
  → SHA-256 dedup (5-minute window)
  → Privacy filter (strip secrets/keys)
  → Store raw observation
  → LLM compress → structured facts + narrative
  → Vector embed → index in BM25 + vector

Stop/SessionEnd hook fires
  → Session summary
  → Knowledge graph extraction
  → Slot reflection

SessionStart fires
  → Load project profile
  → Hybrid search (BM25 + vector + graph)
  → Token budget injection (default 2000 tokens)
```

**4-tier memory consolidation** (modelled on human sleep memory processing):

| Tier | Content |
|------|---------|
| Working | Raw tool observations |
| Episodic | Compressed session summaries |
| Semantic | Extracted facts + patterns |
| Procedural | Workflows + decision patterns |

**Key characteristics:**
- **Zero manual effort** — 12 lifecycle hooks capture everything automatically
- **Ebbinghaus decay** — frequently accessed memories strengthen; stale ones auto-evict
- **No external DBs** — SQLite + in-memory vector index
- **53 MCP tools**, real-time viewer on port 3113
- **95.2% retrieval R@5**, 92% fewer tokens vs loading everything

**Gap:** Captures what the agent said and observed at the tool-call level. Does not distill runs into reusable task recipes. Observations can be noisy; no structured `solution_steps/pitfalls` abstraction.

---

## 3. Mem0

**Approach: Conversation-driven ADD-only extraction with multi-signal retrieval**

The April 2026 algorithm revision made notable changes:
- **ADD-only** — no more UPDATE/DELETE decisions per memory. Memories accumulate; nothing is overwritten. One LLM call per ingestion.
- **What gets stored:** conversations and assistant-confirmed facts. Schema is open-ended — whatever the LLM extracts from the dialogue.
- **Retrieval:** triple-signal fusion — semantic embedding + BM25 keyword + entity matching, scored in parallel and fused.
- **Entity linking** — entities are extracted, embedded, and linked across memories for retrieval boosting.
- **Temporal reasoning** — time-aware retrieval that ranks the right dated instance for current/past/future queries.
- **Scoping:** memories scoped to users, agents, sessions.
- **Key API:** `memory.add(messages, user_id=...)`, `memory.search(query, filters=...)` — extremely simple surface.

**Reported results:** 26% higher accuracy than OpenAI's memory, 90% token savings.

**Gap:** Captures what was *said*, not the exploration path the agent took. No tool-call trajectory extraction; no task recipe abstraction.

---

## 4. memU

**Approach: Dual-agent architecture — main agent + proactive memory bot running in parallel**

The most architecturally unusual of the group:

```
Main Agent              MemU Bot (runs 24/7 in background)
─────────────           ─────────────────────────────────
1. Receive query   ───► 1. Monitor input/output
2. Execute task    ◄─── 2. Memorize & extract → inject memory
3. Respond         ───► 3. Predict user intent
4. Wait            ◄─── 4. Run proactive tasks (pre-fetch, recommend)
```

**Memory structure** (filesystem metaphor):
```
memory/
├── preferences/        ← facts about the user
├── relationships/      ← contacts, history
├── knowledge/          ← domain expertise, learned skills
└── context/            ← recent conversations, pending tasks
```

**Two retrieval modes:**
- `method="rag"` — sub-second embedding similarity, runs continuously without LLM cost
- `method="llm"` — LLM infers what the user needs *before they ask*, with query evolution and early termination

**Key differentiator:** the *proactive push* model. memU doesn't wait for queries — it anticipates them. Also does **skill extraction** from execution logs.

**Reported results:** 92% accuracy on the Locomo benchmark.

**Gap:** Knowledge is extracted from conversations and documents, not from agent tool-call trajectories. Proactive model adds infra complexity that doesn't pay off for a batch distillation workload.

---

## 5. Letta (formerly MemGPT)

**Approach: In-context core blocks + archival storage with agent-initiated self-editing**

The conceptually simplest model:

```python
agent = client.agents.create(
    memory_blocks=[
        {"label": "human", "value": "Name: Alice..."},  # Always in context
        {"label": "persona", "value": "I am..."},       # Always in context
    ]
)
```

- **Core memory blocks** — always in context, editable by the agent itself during a run. Fixed size.
- **Archival storage** — unlimited external storage, retrieved on demand via search.
- **Letta Code** (#1 Terminal-Bench) — stores skills as markdown files that can be versioned in git. Agent writes them opportunistically when it learns something reusable.
- **No automatic capture** — the agent decides what to remember and when. No hooks, no offline pipeline.
- **Self-improvement model:** agent edits its own `persona` block and writes skill files over time.

**Gap:** Agent-in-context memory editing is a different paradigm (stateful agent runtime vs. external memory server). Skill creation is opportunistic and unstructured — not the result of systematic offline distillation.

---

## 6. Graphiti / Zep

**Approach: Temporal knowledge graph — facts as entity-relationship triplets with validity windows**

The most principled approach to the staleness problem:

```
Episode (raw input)
   ↓  LLM extraction
Entity nodes ←→ Relationship edges (with valid_from, valid_until)
   ↓
When info changes → old edge invalidated (not deleted), new edge created
```

**Core data model:**

| Type | What it stores |
|------|----------------|
| Episodes | Raw ingested data (provenance — every fact traces back here) |
| Entities | Nodes: people, products, files, concepts (with evolving summaries) |
| Facts/Relationships | Triplets: `(Entity → Relationship → Entity)` with temporal validity windows |
| Custom Types | Domain-specific node/edge schemas |

**Reported results:** 94.8% on the Deep Memory Retrieval benchmark, up to 90% latency reduction.

**Key insight for this project:** tagging each `key_file` with a `last_verified_commit` hash directly applies Graphiti's temporal tagging idea without requiring Neo4j. At retrieval time, check if `last_verified_commit` is still in git history — if not, flag the memory as "stale, verify before use."

**Gap:** Requires Neo4j (or a managed graph DB). Overkill for the simple use case of tracking whether a file path still exists. The full graph model is designed for conversational + business data, not for code agent tool-call sequences.

---

## 7. qmd

**Approach: Local-first search engine combining BM25, vector search, query expansion, and LLM reranking**

- Indexes markdown, notes, and knowledge bases from the local filesystem.
- Exposes an MCP server: `qmd_search`, `qmd_vector_search`, `qmd_deep_search`, `qmd_get`.
- Combines BM25 full-text + vector semantic + query expansion + LLM reranking — all local, no external services.
- Designed explicitly for agentic flows.
- 11k+ GitHub stars.

**Key insight for this project:** qmd's retrieval design (BM25 + vector + reranking) is exactly what the project proposal calls for at the retrieval layer. This validates the hybrid retrieval architecture — a well-adopted open-source project converged on the same stack independently.

**Gap:** Indexes from documents; does not distill from agent trajectories. No memory schema. No confidence/staleness model. Content is human-authored, not agent-distilled.

---

## 8. OpenViking

**Approach: Filesystem-paradigm context database with tiered (L0/L1/L2) loading**

- Developed by ByteDance Volcengine; open-source implementation of the context layer for OpenClaw coding agents.
- 4.4k+ GitHub stars.
- **`viking://` filesystem metaphor** unifies memories, resources, and skills.
- **Tiered context loading (L0/L1/L2):**
  - L0 — one-sentence abstract (~50 tokens), always returned
  - L1 — short overview with file references (~200 tokens), returned on request
  - L2 — full memory object, returned on explicit `get`
- Directory recursive retrieval, visualized retrieval trajectories, automatic session management with memory extraction.

**Reported results:** 43% task completion improvement, 91% token reduction.

**Key insight for this project:** L0/L1/L2 progressive disclosure is directly applicable. `memory_lookup` returns L0 only (top-5); the agent calls `memory_get(id)` only for memories it actually wants to use.

**Gap:** Knowledge derived from session compression and user/agent interactions, not from tool-call trajectory distillation. No structured `solution_steps/pitfalls` abstraction.

---

## 9. Head-to-Head Comparison

| Dimension | GitHub Copilot | agentmemory | Mem0 | memU | Letta | Graphiti | qmd | OpenViking | **project Proposal** |
|-----------|---------------|-------------|------|------|-------|----------|-----|------------|-------------------|
| **Write trigger** | Agent-initiated | Auto hooks | Conversation ingestion | Parallel bot | Agent-initiated | Conversation ingestion | Manual index | Session compression | Offline batch post-run + `memory_add` |
| **Memory content** | Fact + citations | Observations + summaries | Open-ended LLM extraction | Categorized user facts/skills | Core blocks + skill files | Entity-relationship triplets | Documents + notes | Sessions + skills | Task pattern + solution steps + pitfalls + key files |
| **Trajectory distillation** | ✗ | Partial (session summary only) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **✓ Full tool-call sequence → structured recipe** |
| **Staleness handling** | JIT citation verify | Ebbinghaus decay + eviction | ADD-only accumulation | Continuous update | Agent self-edits | Temporal validity windows | N/A | Session refresh | Confidence scoring + `last_verified_commit` on key files |
| **Retrieval** | Load recent memories | BM25 + vector + graph | Semantic + BM25 + entity | RAG or LLM proactive | Embedding search | Graph traversal + similarity | BM25 + vector + rerank | L0/L1/L2 tiered | BM25 + vector + RRF + cross-encoder reranker |
| **Progressive disclosure** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ L0/L1/L2 | **✓ L0/L1/L2 (from project design + OpenViking confirmation)** |
| **MCP server** | ✓ | ✓ (53 tools) | ✓ OpenMemory | ✗ | ✗ | ✗ | ✓ | ✗ | **✓ 6 focused tools** |
| **External DB required** | Cloud (GitHub) | SQLite only | Optional cloud | Cloud | Cloud/local | Neo4j | Local files | Local | ChromaDB + BM25 (local) |
| **Code-agent focus** | ✓ | ✗ general | ✗ general | Partial | ✓ Letta Code | ✗ general | ✗ general | ✓ OpenClaw | **✓ Repo-level, task-centric** |
| **Unique differentiator** | JIT citation verify | Auto-capture at zero effort | Simplicity + scale (100k devs) | Proactive push | Agent self-editing | Temporal graph | Validated retrieval stack | Token-efficient L0/L1/L2 | **Trajectory → reusable task recipe** |

---

## 10. What to Borrow

Three ideas worth incorporating without changing the core project architecture:

### From Graphiti — commit-hash staleness on `key_files`

the project's original proposal uses time-based confidence decay, which is blind to actual code change. Graphiti's insight: tag facts with explicit validity markers.

**Applied:** each `key_file` stores `last_verified_commit` and `last_verified_at`. At retrieval time, check if the commit is still in git history. If not, flag the memory as "stale — verify before use." This is JIT verification (like GitHub Copilot does for citations) applied to file paths.

```python
"key_files": [
  {
    "path": "src/auth/SecurityConfig.java",
    "last_verified_commit": "a3f4b2c",
    "last_verified_at": "2025-11-01"
  }
]
```

### From OpenViking — L0/L1/L2 progressive disclosure

Store two extra fields at distillation time: a one-sentence abstract (L0, ~50 tokens) and a short overview (L1, ~200 tokens). `memory_lookup` returns L0 only by default; the agent calls `memory_get(id)` only for memories it wants to use. Reduces token waste on irrelevant matches.

```python
# memory_lookup response (L0 only, top-5)
[{"id": "...", "task_pattern": "...", "abstract": "Fixes auth failures by...", "score": 0.92}]

# memory_get response (full L2)
{"id": "...", "solution_steps": [...], "pitfalls": [...], ...}
```

> Note: the project's own diagrams (Diagram 1) already show Progressive Return L0→L1→L2 in the retrieval pipeline. OpenViking's implementation independently confirms this is the right design.

### From Mem0 / agentmemory — online write path alongside offline distillation

the project's proposal includes `memory_add` as an MCP tool but treats offline distillation as the primary write path. Make both first-class: offline distillation for thorough post-run extraction; `memory_add` for when the agent discovers something reusable mid-session. agentmemory's hook model shows agents that can write opportunistically build richer stores faster.

---

## 11. What to Skip

| System | What to skip | Why |
|--------|--------------|-----|
| Graphiti | Full temporal knowledge graph (Neo4j) | Neo4j dependency is overkill for tracking file-path staleness; `last_verified_commit` captures the insight at near-zero cost |
| memU | Parallel proactive memory bot | Infra complexity; diminishing returns for a batch distillation model that already runs offline |
| Letta | Core memory blocks + agent self-editing paradigm | Different architectural paradigm (stateful agent runtime); not compatible with the MCP server model |
| qmd | Full architecture reimplementation | Its retrieval design is already what project proposes — adopting it wholesale means reimplementing qmd, not building something differentiated |
| agentmemory | 53-tool MCP surface | Over-engineered for the demo; 6 focused tools cover the necessary surface |
| Mem0 | ADD-only open-ended schema | Structured distillation (solution_steps, pitfalls) is the differentiator — an open-ended LLM extraction schema loses this intentionally |

---

## Net Assessment

The project proposal's **unique angle** — trajectory distillation into reusable `(task_pattern, solution_steps, pitfalls)` recipes — is not replicated by any of the eight surveyed systems. All other systems capture what the agent *said or observed*; none distill a complete run into a structured, generalizable task recipe.

The three additions (commit-hash staleness, explicit L0/L1/L2 contract, online `memory_add` path) extend the baseline without altering the core architecture. They contribute:

1. Staleness detection that responds to actual code changes (not just elapsed time)
2. Token-efficient retrieval validated by both OpenViking's benchmarks and the project's own diagram
3. Both online (mid-session) and offline (post-run) memory write paths
