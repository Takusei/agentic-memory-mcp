import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class DistilledMemory(BaseModel):
    """Structured output schema for reusable task-memory extraction."""

    task_pattern: str
    description: str
    key_files: list[str] = Field(default_factory=list)
    solution_steps: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)
    lexical_anchors: list[str] = Field(default_factory=list)
    outcome: Literal["success", "partial", "failure"] = "success"

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

TRAJECTORY:
{flattened_trace}
"""


def _dump_structured_result(result) -> dict:
    if isinstance(result, DistilledMemory):
        return result.model_dump()
    if isinstance(result, dict):
        return DistilledMemory.model_validate(result).model_dump()
    raise TypeError(f"Unsupported structured output type: {type(result)!r}")


def _parse_json_result(content: str) -> dict:
    content = (
        content.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    try:
        payload = json.loads(content)
        return DistilledMemory.model_validate(payload).model_dump()
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON response: {content[:200]}") from exc
    except ValidationError as exc:
        raise ValueError(f"LLM returned invalid memory payload: {exc}") from exc


def distill(flattened_trace: str, llm) -> dict:
    """Call LLM with structured output and return parsed memory fields.

    Args:
        flattened_trace: Output of ``flatten_trace()``.
        llm: Any LangChain LLM / ChatModel. Models with
             ``.with_structured_output()`` use the Pydantic schema directly;
             other models fall back to JSON parsing.

    Returns:
        Parsed dict with TaskMemory fields.

    Raises:
        ValueError: If the LLM response cannot be parsed or validated.
    """
    prompt = DISTILLATION_PROMPT.format(flattened_trace=flattened_trace)

    with_structured_output = getattr(llm, "with_structured_output", None)
    if callable(with_structured_output):
        try:
            structured_llm = with_structured_output(DistilledMemory)
            return _dump_structured_result(structured_llm.invoke(prompt))
        except (TypeError, ValidationError, AttributeError):
            pass

    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    return _parse_json_result(content)
