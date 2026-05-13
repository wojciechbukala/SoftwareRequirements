#!/usr/bin/env python3
"""Standalone entry point for FleetRouter."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fleetrouter.cli import main

if __name__ == "__main__":
    main()
