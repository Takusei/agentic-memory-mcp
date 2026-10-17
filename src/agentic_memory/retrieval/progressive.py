from agentic_memory.schema import TaskMemory


def format_at_level(memory: TaskMemory, score: float, level: str = "L0") -> dict:
    """Format a TaskMemory at the requested progressive disclosure level.

    Levels:
        L0 — abstract only (~50 tokens per result)
        L1 — L0 + key file paths + step/pitfall counts (~200 tokens)
        L2 — full TaskMemory including all steps and pitfalls

    Args:
        memory: The TaskMemory object to format.
        score:  Retrieval/reranking score to include in the output.
        level:  "L0", "L1", or "L2".

    Returns:
        A plain dict suitable for JSON serialisation.
    """
    base: dict = {
        "id": memory.id,
        "task_pattern": memory.task_pattern,
        "description": memory.description,
        "confidence": memory.confidence,
        "score": score,
    }

    if level == "L0":
        return base

    if level == "L1":
        return {
            **base,
            "key_files": [kf.path for kf in memory.key_files],
            "step_count": len(memory.solution_steps),
            "pitfall_count": len(memory.pitfalls),
        }

    # L2 — full object
    return {
        **base,
        "repo_id": memory.repo_id,
        "key_files": [kf.__dict__ for kf in memory.key_files],
        "solution_steps": memory.solution_steps,
        "pitfalls": memory.pitfalls,
        "outcome": memory.outcome,
        "lexical_anchors": memory.lexical_anchors,
        "notes": memory.notes,
        "use_count": memory.use_count,
        "reinforcement_count": memory.reinforcement_count,
        "decay_count": memory.decay_count,
        "source_trace_id": memory.source_trace_id,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
    }
