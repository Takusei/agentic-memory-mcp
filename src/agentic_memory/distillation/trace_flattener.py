import re

# Bookkeeping calls to the agentic-memory MCP server itself. These are stored in
# the raw trace for audit purposes but excluded from the LLM distillation input.
_AGENTIC_MEMORY_TOOL_PATTERN = re.compile(
    r"(?:^|\b)(?:mcp_agentic-memor_)?memory_(?:lookup|get|rate|save_trace|"
    r"worker_status|trace_status|add|update|delete)\s*\("
)


def _strip_agentic_memory_fragments(content: str) -> tuple[str, bool]:
    """Remove memory_* call fragments from a (possibly bundled) tool message.

    A "tool" message may bundle several calls separated by ``;`` or newlines,
    e.g. ``memory_worker_status(); read_file(pom.xml)``. We keep the
    non-memory fragments and drop only the memory ones.

    Returns ``(new_content, only_memory)`` where ``only_memory`` is True when
    every fragment was a memory call (so the message can be dropped entirely).
    """
    parts = re.split(r"(\n|;)", content)
    kept: list[str] = []
    had_fragment = False
    had_non_memory = False

    for part in parts:
        if part in ("\n", ";"):
            if kept and kept[-1] not in ("\n", ";"):
                kept.append(part)
            continue
        if part.strip() == "":
            continue
        had_fragment = True
        if _AGENTIC_MEMORY_TOOL_PATTERN.search(part):
            continue
        had_non_memory = True
        kept.append(part)

    while kept and kept[-1] in ("\n", ";"):
        kept.pop()

    new_content = "".join(kept).strip()
    only_memory = had_fragment and not had_non_memory
    return new_content, only_memory


def sanitize_messages(messages: list[dict]) -> list[dict]:
    """Strip self-referential memory tool fragments from trace messages.

    - A tool message containing only memory_* calls is dropped along with its
      immediate result message.
    - A tool message that bundles memory_* calls with other tooling keeps the
      non-memory fragments and retains its result.
    """
    cleaned: list[dict] = []
    skip_next_result = False

    for message in messages:
        if message.get("role") == "tool":
            new_content, only_memory = _strip_agentic_memory_fragments(
                str(message.get("content", ""))
            )
            if only_memory:
                skip_next_result = True
                continue
            if new_content != message.get("content"):
                message = {**message, "content": new_content}
            cleaned.append(message)
            skip_next_result = False
            continue

        if skip_next_result and message.get("role") == "result":
            skip_next_result = False
            continue

        cleaned.append(message)
        skip_next_result = False

    return cleaned


def flatten_trace(trace: dict) -> str:
    """Convert a raw trace dict into a human-readable linear format for LLM prompts.

    Bookkeeping calls to the agentic-memory MCP server (``memory_*``) are
    filtered out here so distillation focuses on real task-solving steps; the
    raw trace on disk is left untouched.

    Output format::

        Trace ID: {trace_id}
        Repo:     {repo_id}
        Task:     {task}

        [Assistant] ...
        [Tool]      tool_name(args)
        [Result]    ...
        [Final]     ...
    """
    lines = [
        f"Trace ID: {trace.get('trace_id', 'unknown')}",
        f"Repo:     {trace.get('repo_id', 'unknown')}",
        f"Task:     {trace.get('task', 'unknown')}",
        "",
    ]

    role_map = {
        "assistant": "[Assistant]",
        "tool": "[Tool]     ",
        "result": "[Result]   ",
        "final": "[Final]    ",
    }

    for msg in sanitize_messages(trace.get("messages", [])):
        prefix = role_map.get(msg.get("role", ""), f"[{msg.get('role', '?')}]")
        lines.append(f"{prefix} {msg.get('content', '')}")

    return "\n".join(lines)
