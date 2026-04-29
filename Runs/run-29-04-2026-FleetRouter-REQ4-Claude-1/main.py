#!/usr/bin/env python3
"""FleetRouter — daily route planner for courier fleets."""
import sys
from pathlib import Path

from io_handler import read_inputs, write_outputs
from planner import plan


def main() -> None:
    directory = Path(".")
    locations, vehicles, packages, distances = read_inputs(directory)
    routes, undeliverable = plan(locations, vehicles, packages, distances)
    write_outputs(directory, routes, undeliverable, distances)


if __name__ == "__main__":
    main()
