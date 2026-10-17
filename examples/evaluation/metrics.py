from dataclasses import dataclass


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
