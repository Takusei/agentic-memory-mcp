"""Populate the memory store with demo task memories for evaluation.

Usage:
    uv run python scripts/seed_demo_memories.py
"""

import os
import sys
from pathlib import Path

# Allow running as a script from repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

load_dotenv()

from agentic_memory.schema import KeyFile, TaskMemory
from agentic_memory.store.memory_store import MemoryStore

_SPRING_BOOT_MEMORY = TaskMemory(
    repo_id="payment-service",
    task_pattern="Spring Boot 2.x to 3.x migration",
    description=(
        "Migrate Spring Boot from 2.7.x to 3.2.x in a Java service, updating the parent POM, "
        "replacing javax with jakarta namespaces, and refactoring SecurityConfig."
    ),
    key_files=[
        KeyFile(path="pom.xml"),
        KeyFile(path="src/main/java/com/example/config/SecurityConfig.java"),
        KeyFile(path="src/main/resources/application.yml"),
    ],
    solution_steps=[
        "Update spring-boot-starter-parent version in pom.xml from 2.7.x to 3.2.x",
        "Replace all javax.* imports with jakarta.* imports across the codebase",
        "Refactor SecurityConfig: replace WebSecurityConfigurerAdapter with SecurityFilterChain bean",
        "Update application.yml deprecated properties (e.g., spring.datasource.* keys)",
        "Run mvn dependency:tree to check for transitive javax dependencies",
        "Run full test suite and fix any remaining javax/jakarta mismatches",
    ],
    pitfalls=[
        "javax.validation → jakarta.validation: many libraries ship their own copy; check transitive deps",
        "Spring Security 6.x dropped WebSecurityConfigurerAdapter; must migrate to SecurityFilterChain",
        "permitAll() and request matchers API changed in Spring Security 6.x",
        "spring-boot-starter-logging bundles its own log4j; check for version conflicts",
    ],
    lexical_anchors=[
        "pom.xml",
        "SecurityConfig.java",
        "WebSecurityConfigurerAdapter",
        "SecurityFilterChain",
        "jakarta.validation",
        "javax.validation",
        "spring-boot-starter-parent",
    ],
    outcome="success",
    source_trace_id="seed-spring-boot",
)

_LOG4J_MEMORY = TaskMemory(
    repo_id="order-service",
    task_pattern="Log4j CVE-2021-44228 upgrade",
    description=(
        "Upgrade log4j-core from 2.14.1 to 2.17.1 to remediate CVE-2021-44228 (Log4Shell), "
        "including checking transitive dependencies pulled in by spring-boot-starter-logging."
    ),
    key_files=[
        KeyFile(path="pom.xml"),
        KeyFile(path="build.gradle"),
    ],
    solution_steps=[
        "Locate log4j-core version in pom.xml or build.gradle and update to 2.17.1",
        "Run mvn dependency:tree (or ./gradlew dependencies) to find transitive log4j inclusions",
        "Add explicit version override for log4j-core in dependencyManagement if spring-boot-starter-logging bundles it",
        "Verify no test-scoped or plugin-scoped transitive log4j 2.14.x references remain",
        "Run the application and check startup logs confirm log4j 2.17.1 is loaded",
    ],
    pitfalls=[
        "spring-boot-starter-logging bundles its own log4j; an explicit dependency update alone is not sufficient",
        "Some plugins (e.g., spring-boot-maven-plugin) may pull in an older log4j at build time",
        "log4j-api and log4j-core versions must match; updating only one causes runtime errors",
    ],
    lexical_anchors=[
        "pom.xml",
        "build.gradle",
        "log4j-core",
        "CVE-2021-44228",
        "log4shell",
        "spring-boot-starter-logging",
        "dependencyManagement",
    ],
    outcome="success",
    source_trace_id="seed-log4j",
)


EXAMPLE_DATA_DIR = REPO_ROOT / "examples" / "data"


def seed(data_dir: str | None = None) -> None:
    store = MemoryStore(data_dir=data_dir or str(EXAMPLE_DATA_DIR))
    memories = [_SPRING_BOOT_MEMORY, _LOG4J_MEMORY]
    for memory in memories:
        store.upsert(memory)
        print(f"  Seeded: [{memory.id}] {memory.task_pattern}")
    print(f"\nSeeded {len(memories)} memories to {store._memories_dir}")


if __name__ == "__main__":
    seed()
