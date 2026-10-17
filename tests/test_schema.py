"""Tests for agentic_memory.schema."""

from agentic_memory.schema import KeyFile, RetrievalResult, TaskMemory


def test_task_memory_defaults():
    m = TaskMemory()
    assert m.id.startswith("mem-")
    assert len(m.id) == 12  # "mem-" + 8 hex chars
    assert m.created_at  # non-empty ISO string
    assert m.updated_at
    assert m.confidence == 0.8
    assert m.outcome == "success"
    assert m.key_files == []
    assert m.solution_steps == []
    assert m.pitfalls == []


def test_task_memory_unique_ids():
    m1 = TaskMemory()
    m2 = TaskMemory()
    assert m1.id != m2.id


def test_key_file_optional_fields():
    kf = KeyFile(path="pom.xml")
    assert kf.path == "pom.xml"
    assert kf.last_verified_commit is None
    assert kf.last_verified_at is None


def test_key_file_with_commit():
    kf = KeyFile(
        path="pom.xml", last_verified_commit="abc123", last_verified_at="2026-01-01"
    )
    assert kf.last_verified_commit == "abc123"


def test_task_memory_with_fields():
    m = TaskMemory(
        repo_id="payment-service",
        task_pattern="Spring Boot migration",
        description="Migrate from 2.7 to 3.2",
        solution_steps=["step1", "step2"],
        pitfalls=["pitfall1"],
        confidence=0.8,
    )
    assert m.repo_id == "payment-service"
    assert len(m.solution_steps) == 2
    assert m.confidence == 0.8


def test_retrieval_result():
    m = TaskMemory(task_pattern="test")
    r = RetrievalResult(memory=m, score=0.95)
    assert r.score == 0.95
    assert r.cross_repo is False
    assert r.memory is m
