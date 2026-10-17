# Synthetic Learned Workflow / Cross-Repo Recall Case

This fixture verifies that agentic memory can teach an arbitrary workflow that is not knowable from general model knowledge.

The benchmark story:

1. A source repo defines and executes a private workflow named `GLASS_TULIP_ARCHIVE_V1`.
2. The completed source task should be saved as memory, including the workflow name, file movements, cleanup, analysis, and reporting rules.
3. A later repo asks only to apply `GLASS_TULIP_ARCHIVE_V1`.
4. The agent should retrieve the prior memory, apply the workflow without the prompt restating the steps, rate the memory as correct/relevant, and save a validation trace.

## Fixture Layout

- `1-glass-tulip-original` is the source repo where the workflow is fully defined.
- `2-glass-tulip-test` is the working validation repo where the workflow name is referenced but not explained.
- `verified-flow.md` records the expected MCP-backed validation flow.

## Suggested Validation

Use the fixture runner from the repository root:

```text
› $agentic-memory-fixture-runner I wanna test synthetic-workflow
```

The runner should first generate memory from `1-glass-tulip-original`, then apply that memory in `2-glass-tulip-test`.

Before the workflow is applied, `npm test` should fail in the original task folder:

```bash
cd fixtures/synthetic-workflow-case/1-glass-tulip-original
npm test
```

The tests should fail until `GLASS_TULIP_ARCHIVE_V1` is applied. After the agent completes `test-tasks/task-01-learn-glass-tulip.md`, `npm test` should pass and the session should save a memory trace.

Then the validation folder should also fail before memory-guided application:

```bash
cd fixtures/synthetic-workflow-case/2-glass-tulip-test
npm test
```

The tests should fail until the workflow is applied from retrieved memory. After the agent completes `test-tasks/task-01-apply-glass-tulip.md`, `npm test` should pass.

## Evidence

- Image: Historical screenshot omitted
- Codex CLI log: Not included in this distribution
- Terminal text log: Not included in this distribution
