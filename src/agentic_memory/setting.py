"""Central configuration for agentic-memory tunable parameters."""

import os


def _float_env(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


# Storage paths
MEMORY_DATA_DIR = os.getenv("MEMORY_DATA_DIR", "./data")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
TRACE_DIR = os.getenv("TRACE_DIR", "./data/traces")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "task_memories")
CHROMA_SPACE = os.getenv("CHROMA_SPACE", "cosine")

# Retrieval
DEFAULT_LOOKUP_TOP_K = _int_env("DEFAULT_LOOKUP_TOP_K", 5)
DEFAULT_RETRIEVER_TOP_K = _int_env("DEFAULT_RETRIEVER_TOP_K", 5)
RETRIEVAL_CANDIDATE_TOP_K = _int_env("RETRIEVAL_CANDIDATE_TOP_K", 30)
RRF_K = _int_env("RRF_K", 60)
RRF_OUTPUT_LIMIT = _int_env("RRF_OUTPUT_LIMIT", 30)
CONFIDENCE_THRESHOLD = _float_env("CONFIDENCE_THRESHOLD", 0.2)
CROSS_REPO_SCORE_THRESHOLD = _float_env("CROSS_REPO_SCORE_THRESHOLD", 0.3)
MAX_MEMORY_NOTES = _int_env("MAX_MEMORY_NOTES", 10)
QUERY_SENTENCE_MIN_WORDS = _int_env("QUERY_SENTENCE_MIN_WORDS", 6)

# Models
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
DISTILL_MODEL = os.getenv("DISTILL_MODEL", "gpt-4o-mini")
DISTILL_TEMPERATURE = _float_env("DISTILL_TEMPERATURE", 0.0)

# Distillation and merge thresholds
DUPLICATE_THRESHOLD = _float_env("DUPLICATE_THRESHOLD", 0.92)
OVERLAP_THRESHOLD = _float_env("OVERLAP_THRESHOLD", 0.75)
CROSS_PATTERN_MERGE_THRESHOLD = _float_env("CROSS_PATTERN_MERGE_THRESHOLD", 0.95)
MERGE_THRESHOLD = _float_env("MERGE_THRESHOLD", 1.5)
HYBRID_MERGE_TOP_K = _int_env("HYBRID_MERGE_TOP_K", 2)

# Memory quality
DEFAULT_MEMORY_CONFIDENCE = _float_env("DEFAULT_MEMORY_CONFIDENCE", 0.8)
CORRECT_CONFIDENCE_DELTA = _float_env("CORRECT_CONFIDENCE_DELTA", 0.1)
INCORRECT_CONFIDENCE_DELTA = _float_env("INCORRECT_CONFIDENCE_DELTA", -0.3)
PARTIAL_CONFIDENCE_DELTA = _float_env("PARTIAL_CONFIDENCE_DELTA", -0.1)
DUPLICATE_CONFIDENCE_DELTA = _float_env("DUPLICATE_CONFIDENCE_DELTA", 0.05)

# Trace capture
TRACE_RESULT_MAX_CHARS = _int_env("TRACE_RESULT_MAX_CHARS", 2000)

# Background distillation worker
TRACE_STATUS_DB_PATH = os.getenv("TRACE_STATUS_DB_PATH", "./data/trace_status.db")
WORKER_POLL_INTERVAL_SEC = _int_env("WORKER_POLL_INTERVAL_SEC", 5)
WORKER_MAX_ATTEMPTS = _int_env("WORKER_MAX_ATTEMPTS", 3)
WORKER_ENABLED = os.getenv("WORKER_ENABLED", "true").lower() in ("1", "true", "yes")

# Background forgetting worker
# Soft-archives stale / low-value memories on a slow cadence (hourly by default).
MEMORY_ARCHIVE_DIR = os.getenv("MEMORY_ARCHIVE_DIR", "./data/archive")
FORGET_ENABLED = os.getenv("FORGET_ENABLED", "true").lower() in ("1", "true", "yes")
FORGET_POLL_INTERVAL_SEC = _int_env("FORGET_POLL_INTERVAL_SEC", 3600)
# A memory at/below this confidence is eligible for forgetting.
FORGET_CONFIDENCE_FLOOR = _float_env("FORGET_CONFIDENCE_FLOOR", 0.1)
# Days since last activity (last_used_at or updated_at) before "stale".
FORGET_STALENESS_DAYS = _int_env("FORGET_STALENESS_DAYS", 90)
# decay_count at/above this, combined with low confidence, is "repeated_incorrect".
FORGET_DECAY_COUNT_THRESHOLD = _int_env("FORGET_DECAY_COUNT_THRESHOLD", 3)
# Age (days since created_at) past which a never-used memory is forgotten.
FORGET_UNUSED_AGE_DAYS = _int_env("FORGET_UNUSED_AGE_DAYS", 30)
# Grace period: memories younger than this (days) are never forgotten.
FORGET_MIN_AGE_DAYS = _int_env("FORGET_MIN_AGE_DAYS", 7)
# Memories used at least this many times (with healthy confidence) are protected.
FORGET_PROTECT_USE_COUNT = _int_env("FORGET_PROTECT_USE_COUNT", 5)
# Max memories archived per sweep, to bound a single cycle's impact.
FORGET_BATCH_LIMIT = _int_env("FORGET_BATCH_LIMIT", 50)
