"""Log4j CVE-2021-44228 upgrade evaluation scenario."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agentic_memory.schema import KeyFile, TaskMemory
from agentic_memory.store.memory_store import MemoryStore


class Log4jUpgrade:
    name = "Log4j CVE Upgrade"
    repo_id = "order-service"
    task = "Upgrade log4j-core from 2.14.1 to 2.17.1 due to CVE-2021-44228"

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store

    def setup(self) -> None:
        """Seed the Log4j CVE upgrade memory."""
        store = self._store or MemoryStore()
        memory = TaskMemory(
            repo_id=self.repo_id,
            task_pattern="Log4j CVE-2021-44228 upgrade",
            description=(
                "Upgrade log4j-core to 2.17.1 to remediate CVE-2021-44228, "
                "including checking transitive dependencies from spring-boot-starter-logging."
            ),
            key_files=[
                KeyFile(path="pom.xml"),
                KeyFile(path="build.gradle"),
            ],
            solution_steps=[
                "Update log4j-core version to 2.17.1 in pom.xml or build.gradle",
                "Run mvn dependency:tree to find transitive log4j inclusions",
                "Add explicit version override in dependencyManagement if needed",
                "Verify no remaining log4j 2.14.x references",
            ],
            pitfalls=[
                "spring-boot-starter-logging bundles its own log4j; explicit dep update alone is insufficient",
                "log4j-api and log4j-core versions must match",
            ],
            outcome="success",
            source_trace_id="seed-log4j",
        )
        store.upsert(memory)

    def verify(self, result: dict) -> bool:
        """Check that the agent output references the dependency file and correct version."""
        output = str(result).lower()
        required = ["pom.xml", "2.17.1", "log4j"]
        return all(keyword in output for keyword in required)
