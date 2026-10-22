#!/usr/bin/env python3
"""
Root wrapper entrypoint for the evaluation framework.
Delegates directly to evaluation/evaluate.py.
"""
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.evaluate import main

if __name__ == "__main__":
    main()
