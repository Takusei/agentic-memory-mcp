"""Pytest isolation for runtime memory stores.

Some modules create default MemoryStore/VectorStore instances at import time.
Point those defaults at a temporary directory so tests never mutate the real
runtime data/ store used by MCP/Copilot.
"""

import os
import shutil
import tempfile
from pathlib import Path

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="agentic-memory-tests-"))

os.environ["MEMORY_DATA_DIR"] = str(_TEST_DATA_DIR)
os.environ["CHROMA_PERSIST_DIR"] = str(_TEST_DATA_DIR / "chroma")
os.environ["TRACE_DIR"] = str(_TEST_DATA_DIR / "traces")
os.environ["TRACE_STATUS_DB_PATH"] = str(_TEST_DATA_DIR / "trace_status.db")
os.environ["WORKER_ENABLED"] = "false"


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)
