# Examples

This folder contains local demos and mini harnesses for experimentation.

## What Is In This Folder

- `agent/`: in-process memory-augmented LangChain agent.
- `evaluation/`: scenario-based baseline vs memory-augmented evaluation harness.
- `fixtures/`: small demo fixture repos used by example scripts.
- `scripts/`: runnable entry points.
- `data/`: generated example outputs (memories, traces, evaluation artifacts); created when scripts run and not distributed.

## Run Scripts

Run these from the project root:

```bash
uv run python -m examples.scripts.seed_demo_memories
uv run python -m examples.scripts.run_evaluation
uv run python -m examples.scripts.run_agent
uv run python -m examples.scripts.demo_memory_evolution
```

Warm-start full second run for the evolution demo:

```bash
RUN_FULL_WARM_AGENT=1 uv run python -m examples.scripts.demo_memory_evolution
```

## Outputs

- `examples/data/`: default demo memory and trace data.
- `examples/data/evaluation/`: evaluation run outputs.
- `examples/data/agent/`: agent run traces and artifacts.
- `examples/data/demo_evolution/`: cold-start vs warm-start demo outputs.

## Notes

- `run_evaluation` uses simulated behavior by default for fast local runs.
- `run_agent` and `demo_memory_evolution` need `OPENAI_API_KEY`.
- To reset, remove the relevant folder under `examples/data/` and rerun.
