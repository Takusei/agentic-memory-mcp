import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from agentic_memory.setting import DEFAULT_MEMORY_CONFIDENCE


@dataclass
class KeyFile:
    path: str
    last_verified_commit: Optional[str] = (
        None  # Git commit hash when file was last verified valid
    )
    last_verified_at: Optional[str] = None  # ISO date string


@dataclass
class TaskMemory:
    # Identity
    id: str = field(default_factory=lambda: f"mem-{uuid.uuid4().hex[:8]}")
    repo_id: str = ""
    task_pattern: str = ""  # Short label, e.g. "Spring Boot 2.x to 3.x migration"
    description: str = ""  # One sentence, used as L0 abstract

    # Content
    key_files: list[KeyFile] = field(default_factory=list)
    solution_steps: list[str] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    outcome: str = "success"  # "success" | "partial" | "failure"

    # Retrieval fields (generated at distillation time, stored separately)
    lexical_anchors: list[str] = field(
        default_factory=list
    )  # file paths, class names, grep patterns

    # Quality signals
    # 0.0–1.0; boosted by duplicates, decayed by incorrect ratings
    confidence: float = DEFAULT_MEMORY_CONFIDENCE
    use_count: int = 0
    reinforcement_count: int = 0
    decay_count: int = 0

    # Feedback notes from memory_rate calls
    notes: list[str] = field(default_factory=list)

    # Provenance
    source_trace_id: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # Last time this memory was actually used (set on memory_rate). Empty until
    # first rated; recency-based forgetting falls back to updated_at when empty.
    last_used_at: str = ""

    # Forgetting / archival metadata (populated only when archived)
    archived_at: str = ""
    forget_reason: str = ""


@dataclass
class RetrievalResult:
    """Returned by HybridRetriever.search() — a memory plus its retrieval score."""

    memory: TaskMemory
    score: float
    cross_repo: bool = False
