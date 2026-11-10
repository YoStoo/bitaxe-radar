#!/usr/bin/env python3
"""Rebuild data/eval_history.json from saved eval result files. See evals/build_history.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
import build_history  # noqa: E402

if __name__ == "__main__":
    sys.exit(build_history.main())
