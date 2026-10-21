#!/usr/bin/env python3
"""
Root entrypoint for the evaluation framework.
Executes the evaluation suite pointing to data/eval/.
"""
from evaluation.evaluate import print_banner, run_evaluation

if __name__ == "__main__":
    print_banner()
    run_evaluation("data/eval")
