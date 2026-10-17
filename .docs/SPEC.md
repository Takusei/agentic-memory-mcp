# Self-Evolving Agentic Memory — Full Implementation Spec

> Initial implementation specification for Agentic Memory MCP.  
> This spec fully describes the system to build. An agent reading this file should be able to implement the entire project without additional design decisions.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Project Layout](#2-project-layout)
3. [Memory Schema](#3-memory-schema)
4. [Storage Layer](#4-storage-layer)
5. [Trajectory Capture (LangChain Callbacks)](#5-trajectory-capture-langchain-callbacks)
6. [Offline Distillation Pipeline](#6-offline-distillation-pipeline)
7. [MCP Memory Server](#7-mcp-memory-server)
8. [Retrieval Pipeline](#8-retrieval-pipeline)
9. [Memory-Augmented Agent](#9-memory-augmented-agent)
10. [Feedback Loop (memory_rate)](#10-feedback-loop-memory_rate)
11. [Evaluation Suite](#11-evaluation-suite)
12. [Demo Scenarios](#12-demo-scenarios)
13. [Dependencies & Configuration](#13-dependencies--configuration)
14. [Phase II / Phase III Roadmap](#14-phase-ii--phase-iii-roadmap)

---

## 1. System Overview

### The Problem
In large engineering organizations, coding agents may run across many repositories. Every run re-explores the same codebase from scratch — reading the same files, re-discovering the same pitfalls, and re-deriving the same solutions. An AI gateway can record agent-session traces for observability. This design explores reusing those traces as task memory.

### The Insight
A successful agent trajectory contains, by definition, the solution to the task it was given. A long trajectory that upgrades a framework version contains exactly the same information as a short summary of how to perform that upgrade — the difference is only density. We can distill trajectories into compact, structured task memories, and project that knowledge forward to future agents.

### The Two Paths

```
RUNTIME (Synchronous)                     OFFLINE (Asynchronous)
─────────────────────────────────────     ──────────────────────────────────
User Task                                 Completed trajectory
   │                                          │
   ▼                                          ▼
memory_lookup()                           Flatten Messages
   │                                          │
   ▼                                          ▼
Reformulate Query                         LLM Distillation
   │                                          │
   ├─► BM25 Search ──┐                        ▼
   └─► Vector Search ─┤                   Query Knowledge Store
                      ▼                       │
                 RRF Fusion              Match? ──Duplicate──► Reinforce Score
                      │                  │                          │
                      ▼                  ├──Overlap──► Merge New Info ─► Store
                Cross-Encoder             │
                Reranker                  └──Novel──► Create Entry ──► Store
                      │
                  Top 5
                      │
                      ▼
            Progressive Return
            (L0 → L1 → L2)
                      │
                      ▼
         Memory-Augmented Agent
         Execution
                      │
              ┌───────┴────────┐
              │                │
         Feedback           New Trajectory
         (memory_rate)       (→ offline distillation)
              │
         Reinforce / Decay
         Knowledge Store
```

---

## 2. Project Layout

```
agentic-memory-mcp/
├── SPEC.md                         # This file
├── README.md                       # Project overview and quick-start
├── pyproject.toml                  # Dependencies (managed with uv)
│
├── agentic_memory/
│   ├── __init__.py
│   │
│   ├── schema.py                   # Memory dataclass / TypedDict definitions
│   │
│   ├── store/
│   │   ├── __init__.py
│   │   ├── vector_store.py         # ChromaDB wrapper
│   │   ├── bm25_store.py           # rank_bm25 wrapper
│   │   └── memory_store.py         # Unified read/write API over both stores
│   │
│   ├── distillation/
│   │   ├── __init__.py
│   │   ├── callback_handler.py     # LangChain BaseCallbackHandler (trace capture)
│   │   ├── trace_flattener.py      # Raw trace → flat message list
│   │   ├── llm_distiller.py        # LLM extraction prompt + structured output
│   │   └── pipeline.py             # Orchestrates: flatten → distill → dedup → upsert
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── query_reformulator.py   # Optional LLM query rewrite
│   │   ├── hybrid_retriever.py     # BM25 + vector in parallel, RRF fusion
│   │   ├── reranker.py             # Cross-encoder reranker (sentence-transformers)
│   │   └── progressive.py          # L0 / L1 / L2 disclosure logic
│   │
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   └── server.py               # FastMCP server exposing all memory tools
│   │
│   └── agent/
│       ├── __init__.py
│       └── memory_agent.py         # LangChain agent wired with memory tools
│
├── evaluation/
│   ├── __init__.py
│   ├── scenarios/
│   │   ├── spring_boot_migration.py
│   │   ├── log4j_upgrade.py
│   │   └── add_endpoint.py
│   ├── metrics.py                  # trajectory_length, tool_calls, token_count
│   └── runner.py                   # Run without memory vs. with memory, print table
│
├── tests/
│   ├── test_schema.py
│   ├── test_store.py
│   ├── test_distillation.py
│   ├── test_retrieval.py
│   └── test_mcp_tools.py
│
├── scripts/
│   ├── seed_demo_memories.py       # Populate store with demo memories
│   └── run_evaluation.py           # Run full evaluation suite and print results
│
└── investigation/                  # Original requirements and research (do not modify)
    └── original_requirements/
```

---

## 3. Memory Schema

### 3.1 Core Memory Object

Defined in `agentic_memory/schema.py`.

```python
from dataclasses import dataclass, field
from typing import Optional
import uuid
from datetime import datetime


@dataclass
class KeyFile:
    path: str
    last_verified_commit: Optional[str] = None   # Git commit hash when file was last verified valid
    last_verified_at: Optional[str] = None        # ISO date string


@dataclass
class TaskMemory:
    # Identity
    id: str = field(default_factory=lambda: f"mem-{uuid.uuid4().hex[:8]}")
    repo_id: str = ""
    task_pattern: str = ""       # Short label, e.g. "Spring Boot 2.x to 3.x migration"
    description: str = ""        # One sentence, used as L0 abstract

    # Content
    key_files: list[KeyFile] = field(default_factory=list)
    solution_steps: list[str] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    outcome: str = "success"     # "success" | "partial" | "failure"

    # Retrieval fields (generated at distillation time, stored separately)
    lexical_anchors: list[str] = field(default_factory=list)  # file paths, class names, grep patterns

    # Quality signals
    confidence: float = 1.0      # 0.0–1.0; boosted by duplicates, decayed by incorrect ratings
    use_count: int = 0
    reinforcement_count: int = 0
    decay_count: int = 0

    # Provenance
    source_trace_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
```

### 3.2 Indexable Passages

Each `TaskMemory` is split into **four passages** for indexing. This allows matching on task type, files, steps, or pitfalls separately. Prefix each passage with `"{tech_context} | "` to disambiguate across repos.

```
Passage 1 (task):     "{tech_context} | {task_pattern}. {description}"
Passage 2 (files):    "{tech_context} | {space-joined key_file paths}"
Passage 3 (steps):    "{tech_context} | {space-joined solution_steps keywords}"
Passage 4 (pitfalls): "{tech_context} | {space-joined pitfalls keywords}"
```

Example for the Spring Boot migration:
```
[P1] Java Spring Boot | Spring Boot 2.x to 3.x migration. Migrate Spring Boot from 2.7.x to 3.2.x.
[P2] Java Spring Boot | pom.xml src/main/java/.../SecurityConfig.java src/main/resources/application.yml
[P3] Java Spring Boot | Update spring-boot-starter-parent Replace javax with jakarta Refactor SecurityConfig WebSecurityConfigurerAdapter SecurityFilterChain
[P4] Java Spring Boot | javax.validation jakarta.validation transitive dependency Spring Security 6.x permitAll request matchers
```

All four passages share the same `memory_id`. Retrieval returns passage IDs; the MCP tool resolves them to full `TaskMemory` objects.

### 3.3 Progressive Disclosure Levels

| Level | What is returned | Token budget |
|-------|-----------------|-------------|
| L0 | `id`, `task_pattern`, `description` (one line), `confidence`, `score` | ~50 tokens per result |
| L1 | L0 + `key_files` (paths only) + `len(solution_steps)` + `len(pitfalls)` | ~200 tokens per result |
| L2 | Full `TaskMemory` including all steps and pitfalls | Full object |

`memory_lookup()` returns L0 by default (top 5). Agent calls `memory_get(id)` to fetch L2 for memories it chooses to use.

---

## 4. Storage Layer

### 4.1 Vector Store — ChromaDB

File: `agentic_memory/store/vector_store.py`

- Use `chromadb` with a persistent local directory (`./data/chroma`).
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` via `chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction`.
- One collection: `"task_memories"`.
- Document = passage text. Metadata = `{"memory_id": str, "passage_type": "task"|"files"|"steps"|"pitfalls", "repo_id": str}`.
- Filtering by `repo_id` in metadata is used for repo-scoped vs. cross-repo lookup.

Key methods:
```python
class VectorStore:
    def upsert_passages(self, memory_id: str, passages: dict[str, str], repo_id: str) -> None
    def search(self, query: str, repo_id: str | None, top_k: int = 30) -> list[dict]
        # Returns list of {memory_id, passage_type, score, text}
    def delete(self, memory_id: str) -> None
```

### 4.2 BM25 Store

File: `agentic_memory/store/bm25_store.py`

- Use `rank_bm25` (`BM25Okapi`).
- Index is persisted to `./data/bm25_index.pkl` via `pickle`.
- Tokenize passages with simple whitespace + lowercase split.
- The index is rebuilt from scratch on any upsert/delete (acceptable for demo scale).

Key methods:
```python
class BM25Store:
    def upsert(self, memory_id: str, passages: dict[str, str], repo_id: str) -> None
    def search(self, query: str, repo_id: str | None, top_k: int = 30) -> list[dict]
        # Returns list of {memory_id, passage_type, bm25_score, text}
    def delete(self, memory_id: str) -> None
    def save(self) -> None
    def load(self) -> None
```

### 4.3 Unified Memory Store

File: `agentic_memory/store/memory_store.py`

Stores full `TaskMemory` objects as JSON in `./data/memories/{memory_id}.json`. Wraps both vector and BM25 stores.

```python
class MemoryStore:
    def upsert(self, memory: TaskMemory) -> None
        # 1. Serialize memory to JSON, write to ./data/memories/
        # 2. Build 4 passages
        # 3. Call vector_store.upsert_passages() and bm25_store.upsert()

    def get(self, memory_id: str) -> TaskMemory | None
        # Load from ./data/memories/{memory_id}.json

    def update_confidence(self, memory_id: str, delta: float) -> None
        # Load, modify confidence (clamp 0.0–1.0), save

    def delete(self, memory_id: str) -> None
        # Remove JSON file, remove from both indexes

    def list_all(self, repo_id: str | None = None) -> list[TaskMemory]
```

---

## 5. Trajectory Capture (LangChain Callbacks)

File: `agentic_memory/distillation/callback_handler.py`

Captures the full agent trajectory without external services. Implements `BaseCallbackHandler`.

```python
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from typing import Any
import json


class TrajectoryCapture(BaseCallbackHandler):
    """
    Captures LangChain agent execution as a flat message list.
    Attach to any LangChain agent via callbacks=[TrajectoryCapture()].
    """

    def __init__(self, trace_id: str, repo_id: str, task: str):
        self.trace_id = trace_id
        self.repo_id = repo_id
        self.task = task
        self.messages: list[dict] = []
        self.tool_calls: int = 0
        self.total_tokens: int = 0

    def on_llm_start(self, serialized, prompts, **kwargs):
        pass  # Not captured individually

    def on_llm_end(self, response: LLMResult, **kwargs):
        for gen_list in response.generations:
            for gen in gen_list:
                text = getattr(gen, "text", "")
                if text:
                    self.messages.append({"role": "assistant", "content": text})
        # Token usage if available
        if response.llm_output and "token_usage" in response.llm_output:
            self.total_tokens += response.llm_output["token_usage"].get("total_tokens", 0)

    def on_tool_start(self, serialized, input_str, **kwargs):
        tool_name = serialized.get("name", "tool")
        self.messages.append({"role": "tool", "content": f"{tool_name}({input_str})"})
        self.tool_calls += 1

    def on_tool_end(self, output: str, **kwargs):
        self.messages.append({"role": "result", "content": str(output)[:2000]})  # truncate large results

    def on_agent_finish(self, finish, **kwargs):
        self.messages.append({"role": "final", "content": str(finish.return_values)})

    def to_trace(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "repo_id": self.repo_id,
            "task": self.task,
            "messages": self.messages,
            "tool_calls": self.tool_calls,
            "total_tokens": self.total_tokens,
        }

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_trace(), f, indent=2)
```

---

## 6. Offline Distillation Pipeline

### 6.1 Trace Flattener

File: `agentic_memory/distillation/trace_flattener.py`

Converts a raw trace dict (from `TrajectoryCapture.to_trace()`) into a formatted string for the LLM prompt.

```python
def flatten_trace(trace: dict) -> str:
    """
    Converts trace messages list into a human-readable linear format.
    
    Output format:
    Trace ID: {trace_id}
    Repo:     {repo_id}
    Task:     {task}
    
    [Assistant] ...
    [Tool]      tool_name(args)
    [Result]    ...
    [Final]     ...
    """
    lines = [
        f"Trace ID: {trace['trace_id']}",
        f"Repo:     {trace['repo_id']}",
        f"Task:     {trace['task']}",
        "",
    ]
    role_map = {
        "assistant": "[Assistant]",
        "tool": "[Tool]     ",
        "result": "[Result]  ",
        "final": "[Final]   ",
    }
    for msg in trace["messages"]:
        prefix = role_map.get(msg["role"], f"[{msg['role']}]")
        lines.append(f"{prefix} {msg['content']}")
    return "\n".join(lines)
```

### 6.2 LLM Distiller

File: `agentic_memory/distillation/llm_distiller.py`

Uses a structured LLM prompt to extract a `TaskMemory` from a flattened trace.

```python
DISTILLATION_PROMPT = """\
You are a knowledge extraction assistant. Analyze the following agent trajectory and extract a reusable task memory.

Rules:
- task_pattern: Short label for the class of task (e.g. "Spring Boot 2.x to 3.x migration")
- description: One sentence summary of what was done (used as L0 abstract)
- key_files: Only files that were essential to the solution (not every file read)
- solution_steps: Ordered, concrete steps that future agents should follow
- pitfalls: Specific mistakes or surprises the agent encountered
- lexical_anchors: Exact strings useful for keyword search (file names, class names, grep patterns)
- outcome: "success", "partial", or "failure"

Respond with valid JSON only. No markdown fences.

TRAJECTORY:
{flattened_trace}

JSON RESPONSE:
"""

def distill(flattened_trace: str, llm) -> dict:
    """
    Call LLM with distillation prompt.
    Returns parsed dict matching TaskMemory fields.
    Raises ValueError if JSON parsing fails.
    """
    prompt = DISTILLATION_PROMPT.format(flattened_trace=flattened_trace)
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    # Strip markdown fences if LLM adds them despite instructions
    content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(content)
```

### 6.3 Deduplication Logic

Three outcomes when inserting a newly distilled memory (implemented in `pipeline.py`):

| Match type | Condition | Action |
|-----------|-----------|--------|
| **Duplicate** | `task_pattern` matches AND cosine similarity of P1 passage > 0.92 | Increment `reinforcement_count` and `confidence += 0.05`, no new entry |
| **Overlap** | Same `task_pattern` AND same `repo_id` AND similarity 0.75–0.92 | Merge: append new pitfalls not already present, update steps if different, update `updated_at` |
| **Novel** | No match above threshold | Create new entry, write to store |

Implementation note: use the vector store to search for `task_pattern` text (Passage 1) with `repo_id` filter, check cosine similarity of top result.

### 6.4 Pipeline Orchestrator

File: `agentic_memory/distillation/pipeline.py`

```python
class DistillationPipeline:
    def __init__(self, memory_store: MemoryStore, llm):
        self.memory_store = memory_store
        self.llm = llm

    def run(self, trace: dict) -> TaskMemory | None:
        """
        Full pipeline:
        1. Flatten trace
        2. Distill with LLM
        3. Check deduplication
        4. Upsert to store
        Returns the upserted/updated memory, or None if distillation fails.
        """
        flattened = flatten_trace(trace)
        try:
            extracted = distill(flattened, self.llm)
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"Distillation failed for trace {trace['trace_id']}: {e}")
            return None

        memory = _dict_to_memory(extracted, trace)
        action = self._dedup_check(memory)

        if action == "duplicate":
            self.memory_store.update_confidence(memory.id, delta=+0.05)
            return None
        elif action == ("overlap", existing_id):
            self._merge(existing_id, memory)
        else:  # novel
            self.memory_store.upsert(memory)

        return memory

    def _dedup_check(self, memory: TaskMemory) -> str | tuple:
        # Query vector store for P1 passage, check similarity thresholds
        ...

    def _merge(self, existing_id: str, new_memory: TaskMemory) -> None:
        # Load existing, add novel pitfalls/steps, update timestamps, re-upsert
        ...
```

---

## 7. MCP Memory Server

File: `agentic_memory/mcp_server/server.py`

Expose all memory operations as MCP tools using `fastmcp`. Start with `python -m agentic_memory.mcp_server.server`.

```python
from fastmcp import FastMCP
from agentic_memory.store.memory_store import MemoryStore
from agentic_memory.retrieval.hybrid_retriever import HybridRetriever

mcp = FastMCP("agentic-memory")
store = MemoryStore()
retriever = HybridRetriever(store)
```

### Tool: `memory_lookup`

```python
@mcp.tool()
def memory_lookup(task: str, repo_id: str, top_k: int = 5) -> list[dict]:
    """
    Search for relevant task memories.
    Returns L0 results (id, task_pattern, description, confidence, score).
    Call memory_get(id) to retrieve full details (L2).
    
    Args:
        task:    Natural language description of the current task.
        repo_id: Repository identifier. Used for repo-scoped search first,
                 then cross-repo fallback if repo results < top_k.
        top_k:   Maximum number of results to return (default 5).
    """
    results = retriever.search(task, repo_id=repo_id, top_k=top_k)
    return [
        {
            "id": r.id,
            "task_pattern": r.task_pattern,
            "description": r.description,   # L0 abstract
            "confidence": r.confidence,
            "score": r.score,
        }
        for r in results
    ]
```

### Tool: `memory_get`

```python
@mcp.tool()
def memory_get(memory_id: str, level: str = "L2") -> dict | None:
    """
    Retrieve a memory by ID at the requested disclosure level.
    
    Args:
        memory_id: Memory ID returned by memory_lookup.
        level:     "L0" (abstract only), "L1" (files + step count), or "L2" (full, default).
    """
    memory = store.get(memory_id)
    if memory is None:
        return None
    if level == "L0":
        return {"id": memory.id, "task_pattern": memory.task_pattern, "description": memory.description}
    if level == "L1":
        return {
            "id": memory.id,
            "task_pattern": memory.task_pattern,
            "description": memory.description,
            "key_files": [kf.path for kf in memory.key_files],
            "step_count": len(memory.solution_steps),
            "pitfall_count": len(memory.pitfalls),
            "confidence": memory.confidence,
        }
    # L2 — full
    return memory.__dict__
```

### Tool: `memory_rate`

```python
@mcp.tool()
def memory_rate(
    memory_id: str,
    factual: str | None = None,
    relevance: str | None = None,
    note: str | None = None,
) -> dict:
    """
    Rate a retrieved memory after use. Drives the feedback loop.
    
    Args:
        memory_id: Memory ID to rate.
        factual:   "correct" | "incorrect" | "partially_correct"
                   "correct" → confidence += 0.1
                   "incorrect" → confidence -= 0.3, flag for re-distillation
                   "partially_correct" → confidence -= 0.1
        relevance: "relevant" | "irrelevant"
                   "irrelevant" → log for retrieval tuning (no confidence change)
        note:      Optional free-text note (e.g. "SecurityConfig.java was moved to config/")
    """
    memory = store.get(memory_id)
    if memory is None:
        return {"ok": False, "error": "not found"}

    delta = 0.0
    needs_redistillation = False

    if factual == "correct":
        delta = +0.1
        memory.use_count += 1
    elif factual == "incorrect":
        delta = -0.3
        needs_redistillation = True
        memory.decay_count += 1
    elif factual == "partially_correct":
        delta = -0.1
        memory.decay_count += 1

    if delta != 0.0:
        store.update_confidence(memory_id, delta)

    if note:
        # Append note to the memory's description for visibility
        memory.description += f" [Note: {note}]"
        store.upsert(memory)

    if needs_redistillation:
        logger.warning(f"Memory {memory_id} flagged for re-distillation: {note}")

    return {"ok": True, "new_confidence": max(0.0, min(1.0, memory.confidence + delta))}
```

### Tool: `memory_add`

```python
@mcp.tool()
def memory_add(
    repo_id: str,
    task_pattern: str,
    description: str,
    key_files: list[str],
    solution_steps: list[str],
    pitfalls: list[str],
    outcome: str = "success",
) -> dict:
    """
    Agent-initiated memory write. Use when you discover something reusable mid-session.
    This is the online write path (complements the offline distillation pipeline).
    
    Args:
        repo_id:        Repository this memory belongs to.
        task_pattern:   Short label for the task class.
        description:    One-sentence abstract (used as L0).
        key_files:      List of essential file paths.
        solution_steps: Ordered steps to solve this class of task.
        pitfalls:       Pitfalls or surprises to warn future agents about.
        outcome:        "success" | "partial" | "failure"
    """
    memory = TaskMemory(
        repo_id=repo_id,
        task_pattern=task_pattern,
        description=description,
        key_files=[KeyFile(path=p) for p in key_files],
        solution_steps=solution_steps,
        pitfalls=pitfalls,
        outcome=outcome,
        source_trace_id="agent-initiated",
    )
    store.upsert(memory)
    return {"ok": True, "memory_id": memory.id}
```

### Tool: `memory_update`

```python
@mcp.tool()
def memory_update(memory_id: str, **fields) -> dict:
    """
    Update specific fields of an existing memory.
    Accepted fields: description, key_files (list[str]), solution_steps, pitfalls, outcome.
    """
    memory = store.get(memory_id)
    if memory is None:
        return {"ok": False, "error": "not found"}
    for k, v in fields.items():
        if k == "key_files":
            memory.key_files = [KeyFile(path=p) for p in v]
        elif hasattr(memory, k):
            setattr(memory, k, v)
    memory.updated_at = datetime.utcnow().isoformat()
    store.upsert(memory)
    return {"ok": True}
```

### Tool: `memory_delete`

```python
@mcp.tool()
def memory_delete(memory_id: str) -> dict:
    """
    Delete a memory from the knowledge store. Use when a memory is confirmed stale.
    """
    store.delete(memory_id)
    return {"ok": True}
```

---

## 8. Retrieval Pipeline

File: `agentic_memory/retrieval/hybrid_retriever.py`

### 8.1 Query Reformulation (optional)

If the task query is short and keyword-heavy (e.g. `"spring boot upgrade 2.7 3.2"`), optionally rewrite to a natural language question before vector search to improve neural recall.

```python
REFORMULATE_PROMPT = """\
Rewrite the following task description as a natural-language question suitable for semantic search.
Task: {task}
Question (one sentence, no markdown):"""
```

This step is optional. Skip if the task is already a full sentence.

### 8.2 BM25 + Vector Parallel Search

Both searches run on the same query against the same passage corpus.

1. `bm25_store.search(query, repo_id=repo_id, top_k=30)` — BM25 over all 4 passage types
2. `vector_store.search(query, repo_id=repo_id, top_k=30)` — Cosine similarity

Both return lists of `{memory_id, passage_type, score, text}`.

If `repo_id` is given:
- First search with metadata filter `repo_id = repo_id`
- If results < `top_k`, also search without filter (cross-repo fallback)
- Mark cross-repo results with `{"cross_repo": True}` in response

### 8.3 RRF Fusion

```python
def rrf_fusion(
    bm25_results: list[dict],
    vector_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """
    Reciprocal Rank Fusion.
    score(d) = sum(1 / (k + rank(d))) across all result lists.
    Deduplicates by memory_id (keep highest-ranked passage per memory).
    Returns merged list sorted by fused score, top 30.
    """
    scores: dict[str, float] = {}
    for rank, result in enumerate(bm25_results):
        mid = result["memory_id"]
        scores[mid] = scores.get(mid, 0.0) + 1.0 / (k + rank + 1)
    for rank, result in enumerate(vector_results):
        mid = result["memory_id"]
        scores[mid] = scores.get(mid, 0.0) + 1.0 / (k + rank + 1)
    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [{"memory_id": mid, "rrf_score": scores[mid]} for mid in sorted_ids[:30]]
```

### 8.4 Cross-Encoder Reranker

File: `agentic_memory/retrieval/reranker.py`

Use `sentence-transformers` cross-encoder for final reranking.

```python
from sentence_transformers import CrossEncoder

MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

class Reranker:
    def __init__(self):
        self._model = None  # Lazy load

    @property
    def model(self):
        if self._model is None:
            self._model = CrossEncoder(MODEL)
        return self._model

    def rerank(self, query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
        """
        candidates: list of {memory_id, rrf_score, description (L0 text)}
        Returns top_k sorted by cross-encoder score.
        """
        pairs = [(query, c["description"]) for c in candidates]
        scores = self.model.predict(pairs)
        for i, c in enumerate(candidates):
            c["rerank_score"] = float(scores[i])
        return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:top_k]
```

### 8.5 Full Search Flow

```python
class HybridRetriever:
    def search(self, query: str, repo_id: str, top_k: int = 5) -> list[RetrievalResult]:
        # 1. Optional reformulation
        search_query = self._maybe_reformulate(query)

        # 2. Parallel BM25 + vector
        bm25 = self.bm25_store.search(search_query, repo_id, top_k=30)
        vec  = self.vector_store.search(search_query, repo_id, top_k=30)

        # 3. RRF fusion
        fused = rrf_fusion(bm25, vec)

        # 4. Load L0 descriptions for reranking
        candidates = []
        for item in fused:
            memory = self.memory_store.get(item["memory_id"])
            if memory and memory.confidence > 0.1:  # Filter out very low confidence
                candidates.append({**item, "description": memory.description})

        # 5. Rerank
        reranked = self.reranker.rerank(query, candidates, top_k=top_k)

        # 6. Load full memories and build results
        results = []
        for item in reranked:
            memory = self.memory_store.get(item["memory_id"])
            if memory:
                results.append(RetrievalResult(memory=memory, score=item["rerank_score"]))
        return results
```

---

## 9. Memory-Augmented Agent

File: `agentic_memory/agent/memory_agent.py`

A LangChain `ReAct`-style agent equipped with the memory MCP tools plus standard code exploration tools.

### 9.1 Tool Setup

Expose MCP tools as LangChain tools using `langchain_mcp_adapters` (or direct function wrappers):

```python
from langchain.tools import Tool

memory_tools = [
    Tool(name="memory_lookup", func=memory_lookup_fn,
         description="Look up task memories before exploring. Call this first with the task description and repo_id."),
    Tool(name="memory_get", func=memory_get_fn,
         description="Retrieve full details of a memory by ID. Use L2 for complete steps and pitfalls."),
    Tool(name="memory_rate", func=memory_rate_fn,
         description="Rate a memory after using it. Always call this to close the feedback loop."),
    Tool(name="memory_add", func=memory_add_fn,
         description="Write a new memory when you discover something reusable."),
]

code_tools = [
    # Standard tools: grep_search, read_file, list_dir, write_file
    ...
]

all_tools = memory_tools + code_tools
```

### 9.2 System Prompt

```
You are a memory-augmented code agent. You have access to a knowledge store of past task solutions.

WORKFLOW:
1. ALWAYS call memory_lookup() first with the task and repo_id before any code exploration.
2. If results are returned, call memory_get(id, level="L1") on the top result to see key files.
3. If the memory looks relevant, call memory_get(id, level="L2") to get full solution steps and pitfalls.
4. Apply the steps. Verify that key_files still exist and are relevant.
5. After completing the task, call memory_rate() on every memory you used:
   - factual="correct" if the steps worked
   - factual="incorrect" with a note if files moved or steps were wrong
   - relevance="irrelevant" if the memory was not applicable
6. If you discovered a new reusable pattern not in the store, call memory_add().

If no memory matches, proceed with standard exploration. The resulting trajectory will be
distilled into a new memory automatically.
```

### 9.3 Trajectory Capture Wiring

```python
def run_agent(task: str, repo_id: str) -> dict:
    trace_id = f"trace-{uuid.uuid4().hex[:8]}"
    capture = TrajectoryCapture(trace_id=trace_id, repo_id=repo_id, task=task)

    agent = create_react_agent(llm=llm, tools=all_tools)
    agent_executor = AgentExecutor(agent=agent, tools=all_tools, callbacks=[capture])

    result = agent_executor.invoke({"input": task})

    # Save trace for offline distillation
    trace = capture.to_trace()
    trace_path = f"./data/traces/{trace_id}.json"
    capture.save(trace_path)

    # Optionally run distillation inline (or queue for async processing)
    pipeline.run(trace)

    return {
        "result": result,
        "trace_id": trace_id,
        "tool_calls": capture.tool_calls,
        "total_tokens": capture.total_tokens,
    }
```

---

## 10. Feedback Loop (`memory_rate`)

The feedback loop creates a closed system where every agent run either reinforces or refines the knowledge store:

```
memory_rate(factual="correct")
    └─► confidence += 0.1
    └─► reinforcement_count += 1

memory_rate(factual="incorrect", note="...")
    └─► confidence -= 0.3
    └─► decay_count += 1
    └─► flag for re-distillation (log warning; in Phase II: auto-trigger)

memory_rate(factual="partially_correct")
    └─► confidence -= 0.1
    └─► decay_count += 1

memory_rate(relevance="irrelevant")
    └─► log retrieval miss (for future reranker tuning)
    └─► no confidence change

confidence < 0.2
    └─► memory filtered out of retrieval results (still in store, can be restored)
    └─► in Phase II: auto-deleted after 30 days at low confidence
```

Additionally, the new trajectory from each memory-augmented run re-enters the distillation pipeline. If the agent found a shorter path, the solution steps are refined. If it encountered a new pitfall, it is merged in.

---

## 11. Evaluation Suite

### 11.1 Metrics

File: `evaluation/metrics.py`

```python
@dataclass
class RunResult:
    scenario: str
    with_memory: bool
    trajectory_length: int   # Number of messages in the trace
    tool_calls: int          # Number of tool invocations
    total_tokens: int        # Total LLM tokens consumed
    success: bool            # Did the agent complete the task correctly?
    memories_used: int       # How many memories were retrieved and rated "correct"
    time_seconds: float
```

Primary metric: **trajectory length reduction** = `(N_baseline - N_with_memory) / N_baseline × 100%`

Secondary metrics: tool_calls reduction, token reduction.

### 11.2 Scenarios

Implement in `evaluation/scenarios/`. Each scenario is a class with:
- `name: str`
- `repo_id: str`
- `task: str`
- `setup() -> None` — prepares mock repo / seed memories
- `verify(result: dict) -> bool` — checks if agent output is correct

**Scenario 1: Spring Boot Migration** (`spring_boot_migration.py`)
- Task: "Upgrade Spring Boot from 2.7 to 3.2 in payment-service"
- Seed memory with the full Spring Boot migration memory from §3.1
- Baseline: agent with no memory tool; With memory: agent with memory_lookup
- Verify: agent mentions pom.xml, javax→jakarta, SecurityConfig, application.yml

**Scenario 2: Log4j CVE Upgrade** (`log4j_upgrade.py`)
- Task: "Upgrade log4j-core from 2.14.1 to 2.17.1 due to CVE-2021-44228"
- Seed memory: key files = pom.xml/build.gradle, steps = update version + check transitive deps, pitfall = spring-boot-starter-logging bundles its own log4j
- Verify: agent finds the dependency file and applies the correct version

**Scenario 3: Add REST Endpoint** (`add_endpoint.py`)
- Task: "Add a GET /health endpoint to the order-service"
- No pre-seeded memory (novel task) — tests that agent runs normally without memory and that the resulting trajectory is distilled correctly
- After run: assert that distillation created a new entry in the knowledge store

### 11.3 Evaluation Runner

File: `evaluation/runner.py`

```python
def run_all() -> None:
    scenarios = [SpringBootMigration(), Log4jUpgrade(), AddEndpoint()]
    results = []
    for scenario in scenarios:
        scenario.setup()
        # Baseline (no memory)
        baseline = run_agent_no_memory(scenario.task, scenario.repo_id)
        # With memory
        with_mem = run_agent_with_memory(scenario.task, scenario.repo_id)
        results.append((scenario.name, baseline, with_mem))

    print_comparison_table(results)
```

Output table format:
```
Scenario                   | Baseline Tools | Memory Tools | Tool Reduction | Token Reduction
Spring Boot Migration      |            31  |           8  |         74.2%  |          71.5%
Log4j CVE Upgrade          |            18  |           5  |         72.2%  |          68.0%
Add REST Endpoint (novel)  |            12  |          13  |         N/A    |          N/A
```

---

## 12. Demo Scenarios

### Scenario A: First run (no memory)
1. Start agent on "Upgrade Spring Boot from 2.7 to 3.2"
2. Agent calls `memory_lookup()` → returns empty
3. Agent explores: 31 tool calls, reads 12 files
4. Agent completes task
5. Trajectory is distilled → new memory created

### Scenario B: Second run (memory hit)
1. Start agent on same task (or same class of task in a different repo)
2. Agent calls `memory_lookup()` → returns Spring Boot migration memory (L0)
3. Agent calls `memory_get(id, level="L1")` → sees 3 key files + 4 steps
4. Agent calls `memory_get(id, level="L2")` → gets full steps and pitfalls
5. Agent executes directly: 8 tool calls, reads only the 3 key files
6. Agent calls `memory_rate(factual="correct")` → confidence reinforced

### Scenario C: Stale memory (staleness handling)
1. SecurityConfig.java has been moved to `config/SecurityConfig.java`
2. Agent calls `memory_lookup()` → gets memory with old path
3. Agent tries to read file → file not found
4. Agent calls `memory_rate(memory_id=..., factual="incorrect", note="SecurityConfig.java moved to config/")`
5. Memory confidence drops by 0.3; flagged for re-distillation
6. Agent falls back to grep, finds new location, completes task
7. New trajectory distills updated path into the knowledge store

---

## 13. Dependencies & Configuration

### `pyproject.toml`

```toml
[project]
name = "agentic-memory"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # LangChain
    "langchain>=0.3",
    "langchain-core>=0.3",
    "langchain-openai>=0.2",

    # Vector store
    "chromadb>=0.5",

    # BM25
    "rank-bm25>=0.2",

    # Embeddings + reranker (local, no API cost)
    "sentence-transformers>=3.0",

    # MCP server
    "fastmcp>=2.0",

    # Utilities
    "pydantic>=2.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8",
    "pytest-asyncio",
]
```

### Environment Variables (`.env`)

```bash
# LLM for distillation and agent reasoning
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini          # Used for distillation (cost-efficient)
AGENT_MODEL=gpt-4o                # Used for agent execution

# Storage paths (defaults shown)
MEMORY_DATA_DIR=./data
CHROMA_PERSIST_DIR=./data/chroma
TRACE_DIR=./data/traces

# Retrieval tuning
RRF_K=60
TOP_K_RETRIEVAL=5
CONFIDENCE_THRESHOLD=0.2          # Memories below this are filtered from results
DUPLICATE_THRESHOLD=0.92          # Cosine similarity for duplicate detection
OVERLAP_THRESHOLD=0.75            # Cosine similarity for overlap/merge
```

### Running the System

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install all dependencies
uv sync --all-extras

# Seed demo memories (for evaluation)
uv run python scripts/seed_demo_memories.py

# Start MCP server (for Claude Desktop / Cursor integration)
uv run python -m agentic_memory.mcp_server.server

# Run evaluation suite
uv run python scripts/run_evaluation.py

# Run tests
uv run pytest tests/ -v
```

### MCP Client Configuration (Claude Desktop)

```json
{
  "mcpServers": {
    "agentic-memory": {
      "command": "uv",
      "args": ["run", "python", "-m", "agentic_memory.mcp_server.server"],
      "cwd": "/path/to/agentic-memory-mcp"
    }
  }
}
```

---

## 14. Phase II / Phase III Roadmap

Items below are **intentionally out of scope for Phase I** (the initial proof of concept). They are recorded here so the implementation agent does not attempt them now, and so the design story is complete for the architecture walkthrough.

### Phase II — Operational Hardening

**1. Black-box agent trajectory support (agents not running through an AI gateway)**

Phase I captures trajectories via `TrajectoryCapture(BaseCallbackHandler)` — this only works for LangChain agents we control. Two classes of black-box agents need a different approach:

- **Local MCP-only agents (GitHub Copilot, Cursor, Claude Desktop):** These connect to the MCP server but never expose their chain-of-thought. Plan:
  - Add MCP server-side session logging: record every `memory_lookup`, `memory_get`, and `memory_rate` call with timestamps and session IDs. This gives a behavioral trace (task + memories used + ratings) sufficient to close the feedback loop even without CoT.
  - Rely on `memory_add` as the inline distillation path: prompt these agents (via their system prompt / instructions file) to call `memory_add(task_pattern, solution_steps, pitfalls, ...)` at the end of each successful session. The agent itself becomes the distiller.

- **AI gateway agents (production):** The Gateway already persists the full request/response chain for every session. The Phase II work is an adapter that reads from the Gateway's trace store (instead of local JSON files) and feeds the same `DistillationPipeline`. No changes to the pipeline itself.

| Agent type | Trajectory source | Distillation path | Feedback loop |
|-----------|-------------------|-------------------|---------------|
| LangChain (Phase I demo) | `BaseCallbackHandler` | Offline pipeline | `memory_rate` ✓ |
| AI gateway agents | Gateway trace store adapter | Offline pipeline | `memory_rate` ✓ |
| Local MCP agents (Copilot, Cursor) | MCP server-side call log | Partial (task + ratings) | `memory_rate` ✓ |
| Any MCP agent without gateway | Agent calls `memory_add` | Inline (agent-initiated) | `memory_rate` ✓ |

**2. Automated re-distillation**

Phase I flags memories with `decay_count` and logs warnings when `factual="incorrect"`. Phase II adds:
- A background job that scans for memories with `confidence < 0.4` and queues them for re-distillation from the most recent successful trace for the same `task_pattern`.
- Auto-deletion after 30 days at `confidence < 0.2`.

**3. Cross-repo knowledge propagation**

Phase I stores `repo_id` on every memory and does a cross-repo fallback at retrieval time. Phase II adds:
- A canonicalization step in the pipeline: if the same `task_pattern` appears across 3+ repos with high similarity, create a shared `repo_id="__global__"` entry that all repos inherit.
- Allows a new service with zero prior agent runs to inherit patterns from the whole organisation.

**4. Day-2 operations tooling**
- Admin CLI: `uv run python -m agentic_memory.admin list|inspect|delete|bulk-decay`
- Health endpoint on the MCP server: returns store size, mean confidence, low-confidence memory count.
- Structured logging (JSON) for all distillation and retrieval events, suitable for ingestion into the project's observability stack.

### Phase III — Scale & Intelligence

**1. Replace ChromaDB + rank_bm25 with a production vector database**

Phase I uses local ChromaDB + pickle-serialized BM25 (fine for demo). Phase III migrates to:
- A managed vector DB (Qdrant, Weaviate, or an internal vector service) for horizontal scaling.
- A proper BM25/full-text index (Elasticsearch or OpenSearch) replacing the in-memory BM25 rebuild.

**2. Fine-tuned embedding model for code tasks**

Phase I uses `all-MiniLM-L6-v2` (general English). Phase III fine-tunes an embedding model on the project's distilled task memories using contrastive learning (positive pairs = same task_pattern, different repos; negatives = different task_patterns). Expected retrieval precision improvement: ~15–25%.

**3. Temporal knowledge graph layer (Graphiti-style)**

For high-churn repos where `key_files` move frequently, Phase III optionally adds a lightweight temporal layer:
- Track `(file_path, repo_id) → valid_from, valid_until` using commit timestamps.
- At retrieval time, automatically validate `key_files` against git history and annotate stale paths without requiring an `incorrect` rating from the agent.

**4. Retrieval quality continuous improvement**
- Use `relevance="irrelevant"` ratings (accumulated in Phase I/II) to fine-tune the cross-encoder reranker on domain-specific query–memory pairs.
- A/B test query reformulation: measure whether LLM rewrite improves top-5 precision on held-out tasks.

---

## Appendix: Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vector DB | ChromaDB | Local, no infra, persistent, supports metadata filtering |
| BM25 | rank_bm25 | Pure Python, no server, sufficient for demo scale |
| Embeddings | all-MiniLM-L6-v2 | Local, free, fast, 384-dim, no API cost |
| Reranker | ms-marco-MiniLM-L-6-v2 | Local cross-encoder, strong on passage ranking |
| MCP server | fastmcp | Minimal boilerplate, stdlib-compatible |
| Trace capture | LangChain BaseCallbackHandler | No external service, works with any LangChain agent |
| Dedup thresholds | 0.92 / 0.75 | Conservative: prefer false merge over false duplicate |
| L0/L1/L2 disclosure | Already in project design | Reduces token use when multiple memories match |
| Commit-hash on key_files | `last_verified_commit` field | Staleness detection without periodic re-indexing |
| Agent-initiated writes | `memory_add` MCP tool | Both online and offline write paths, online captures mid-session discoveries |
