"""
FleetRouter – daily route planner for courier companies.

Usage:
    python main.py [input_dir [output_dir]]

Both directories default to the current working directory.

Input files expected in input_dir:
    packages.csv, vehicles.csv, locations.csv, distances.csv

Output files written to output_dir:
    stops_order.csv, undeliverable.csv, summary.csv
"""
import sys
from pathlib import Path

from io_handler import read_inputs, write_outputs
from planner import solve


def main() -> None:
    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")

    output_dir.mkdir(parents=True, exist_ok=True)

    data = read_inputs(input_dir)
    plan = solve(data)
    write_outputs(plan, data, output_dir)


if __name__ == "__main__":
    main()
