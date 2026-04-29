#!/usr/bin/env python3
"""FleetRouter — daily courier route planning tool."""

import argparse
import os
import sys

from reader import load_inputs
from planner import plan
from writer import write_stops_order, write_summary, write_undeliverable


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="fleetrouter",
        description="FleetRouter: daily courier route planning.",
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="<dir>",
        help="Directory containing the four input CSV files.",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="<dir>",
        help="Directory where output CSV files will be written.",
    )
    return parser.parse_args()


def main():
    args = _parse_args()

    if not os.path.isdir(args.input):
        print(
            f"Error: input directory {args.input!r} does not exist.",
            file=sys.stderr,
        )
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    print("Reading and validating input data...")
    locations, vehicles, packages, distances, validation_undeliverable = load_inputs(
        args.input
    )
    print(
        f"  Loaded {len(locations)} location(s), {len(vehicles)} vehicle(s), "
        f"{len(packages)} valid package(s)."
    )

    if not vehicles:
        print("Warning: no valid vehicles — nothing to plan.", file=sys.stderr)

    print("Planning routes...")
    routes, planning_undeliverable = plan(vehicles, packages, distances)

    # Combine undeliverable lists into (package_id, reason) pairs
    all_undeliverable = validation_undeliverable + [
        (pkg.package_id, reason) for pkg, reason in planning_undeliverable
    ]

    print("Writing output files...")
    write_stops_order(routes, args.output)
    write_summary(routes, args.output)
    write_undeliverable(all_undeliverable, args.output)

    delivered = sum(len(r.stops) for r in routes)
    total_processed = len(packages) + len(validation_undeliverable)
    undeliverable_count = len(all_undeliverable)

    print(
        f"\nDone. Packages processed: {total_processed}, "
        f"delivered: {delivered}, "
        f"undeliverable: {undeliverable_count}."
    )


if __name__ == "__main__":
    main()
