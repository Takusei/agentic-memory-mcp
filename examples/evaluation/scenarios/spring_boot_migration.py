"""Spring Boot 2.x → 3.x migration evaluation scenario."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agentic_memory.schema import KeyFile, TaskMemory
from agentic_memory.store.memory_store import MemoryStore


class SpringBootMigration:
    name = "Spring Boot Migration"
    repo_id = "payment-service"
    task = "Upgrade Spring Boot from 2.7 to 3.2 in payment-service"

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store

    def setup(self) -> None:
        """Seed the Spring Boot migration memory."""
        store = self._store or MemoryStore()
        memory = TaskMemory(
            repo_id=self.repo_id,
            task_pattern="Spring Boot 2.x to 3.x migration",
            description=(
                "Migrate Spring Boot from 2.7.x to 3.2.x: update parent POM, "
                "replace javax with jakarta, and refactor SecurityConfig."
            ),
            key_files=[
                KeyFile(path="pom.xml"),
                KeyFile(path="src/main/java/com/example/config/SecurityConfig.java"),
                KeyFile(path="src/main/resources/application.yml"),
            ],
            solution_steps=[
                "Update spring-boot-starter-parent in pom.xml to 3.2.x",
                "Replace javax.* imports with jakarta.* imports",
                "Refactor SecurityConfig from WebSecurityConfigurerAdapter to SecurityFilterChain",
                "Update deprecated application.yml properties",
                "Check transitive javax dependencies with mvn dependency:tree",
                "Run full test suite",
            ],
            pitfalls=[
                "javax.validation → jakarta.validation: check transitive deps",
                "Spring Security 6.x dropped WebSecurityConfigurerAdapter",
                "permitAll() API changed in Spring Security 6.x",
            ],
            outcome="success",
            source_trace_id="seed-spring-boot",
        )
        store.upsert(memory)
        self._seeded_id = memory.id

    def verify(self, result: dict) -> bool:
        """Check that the agent output references the key migration artefacts."""
        output = str(result).lower()
        required = ["pom.xml", "jakarta", "securityconfig"]
        return all(keyword in output for keyword in required)
