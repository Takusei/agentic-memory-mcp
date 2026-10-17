"""Run the full evaluation suite.

Usage:
    uv run python scripts/run_evaluation.py
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

load_dotenv()

from examples.evaluation.runner import run_all

if __name__ == "__main__":
    run_all(data_dir=str(REPO_ROOT / "examples" / "data" / "evaluation"))
