"""Add REST endpoint evaluation scenario (novel task — tests distillation)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agentic_memory.store.memory_store import MemoryStore


class AddEndpoint:
    name = "Add REST Endpoint (novel)"
    repo_id = "order-service"
    task = "Add a GET /health endpoint to the order-service"

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store

    def setup(self) -> None:
        """No pre-seeded memory — tests that the agent runs normally without memory."""
        pass

    def verify(self, result: dict) -> bool:
        """After run, check that distillation created a new entry in the knowledge store.

        In the simulated runner the distillation is triggered manually; we check
        the store was written to.
        """
        store = self._store or MemoryStore()
        memories = store.list_all(repo_id=self.repo_id)
        # Accept as success if at least one memory was created for this repo
        return len(memories) >= 1
