#!/usr/bin/env python3
"""Copilot ADAS Simulation — entry point.

Usage:
    python main.py --input <input_dir> --output <output_dir>
"""
import sys
from pathlib import Path

# Ensure the package directory is on the path when invoked directly
sys.path.insert(0, str(Path(__file__).parent))

from cli import parse_args
from engine import CopilotEngine


def main() -> None:
    args = parse_args()
    engine = CopilotEngine(args.input, args.output)
    engine.run()


if __name__ == "__main__":
    main()
