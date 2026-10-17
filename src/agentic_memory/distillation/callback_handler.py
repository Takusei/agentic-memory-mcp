import json
import logging
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from agentic_memory.setting import TRACE_RESULT_MAX_CHARS

logger = logging.getLogger(__name__)


class TrajectoryCapture(BaseCallbackHandler):
    """
    Captures LangChain agent execution as a flat message list.
    Attach to any LangChain agent via callbacks=[TrajectoryCapture()].
    """

    def __init__(self, trace_id: str, repo_id: str, task: str) -> None:
        super().__init__()
        self.trace_id = trace_id
        self.repo_id = repo_id
        self.task = task
        self.messages: list[dict] = []
        self.tool_calls: int = 0
        self.total_tokens: int = 0

    def on_llm_start(self, serialized: dict, prompts: list[str], **kwargs: Any) -> None:
        pass  # Not captured individually

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        for gen_list in response.generations:
            for gen in gen_list:
                text = getattr(gen, "text", "")
                if text:
                    self.messages.append({"role": "assistant", "content": text})
        # Token usage if available
        if response.llm_output:
            usage = response.llm_output.get("token_usage", {})
            self.total_tokens += usage.get("total_tokens", 0)

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs: Any) -> None:
        tool_name = serialized.get("name", "tool")
        self.messages.append({"role": "tool", "content": f"{tool_name}({input_str})"})
        self.tool_calls += 1

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        # Truncate very large results to avoid bloating traces
        truncated = str(output)[:TRACE_RESULT_MAX_CHARS]
        self.messages.append({"role": "result", "content": truncated})

    def on_agent_finish(self, finish: Any, **kwargs: Any) -> None:
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
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_trace(), f, indent=2)
