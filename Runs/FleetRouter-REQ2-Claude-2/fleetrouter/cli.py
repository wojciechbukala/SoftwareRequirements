"""Command-line interface for FleetRouter."""

import argparse
import sys
from pathlib import Path

from .reader import load_all
from .solver import solve
from .writer import write_all


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FleetRouter – daily route planning for courier companies."
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="<dir>",
        help="Directory containing input CSV files.",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="<dir>",
        help="Directory where output CSV files will be written.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.is_dir():
        print(f"ERROR: Input directory does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)

    # Load and validate all input data
    locations, distances, vehicles, packages, pre_undeliverable = load_all(input_dir)

    total_input = len(packages) + len(pre_undeliverable)
    print(f"Loaded {total_input} packages, {len(vehicles)} vehicles, {len(locations)} locations.")

    # Solve: assign packages to vehicles and build optimized routes
    routes, undeliverable = solve(vehicles, packages, distances)

    # Write output files
    write_all(output_dir, routes, vehicles, distances, undeliverable, pre_undeliverable)

    # Compute summary stats
    delivered = sum(len(pkgs) for pkgs in routes.values())
    total_undeliverable = len(undeliverable) + len(pre_undeliverable)
    total_processed = delivered + total_undeliverable

    print(
        f"Planning complete: {total_processed} packages processed, "
        f"{delivered} delivered, "
        f"{total_undeliverable} undeliverable."
    )
    print(f"Output written to: {output_dir}")


if __name__ == "__main__":
    main()
