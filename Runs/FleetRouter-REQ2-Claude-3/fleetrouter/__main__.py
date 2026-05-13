import argparse
import os
import sys

from .optimizer import optimize_routes
from .planner import assign_packages
from .reader import read_all
from .writer import write_stops_order, write_summary, write_undeliverable


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fleetrouter",
        description="FleetRouter — daily route planning for courier companies.",
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="DIR",
        help="Directory containing the four input CSV files.",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="DIR",
        help="Directory where output CSV files will be written.",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.input):
        print(f"ERROR: Input directory not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    print("Reading input files …")
    packages, vehicles, locations, distances, pre_undeliverable, warnings = read_all(
        args.input
    )

    for warning in warnings:
        print(f"  WARNING: {warning}")

    print(
        f"  {len(locations)} location(s), {len(vehicles)} vehicle(s), "
        f"{len(packages)} valid package(s) loaded."
    )
    if pre_undeliverable:
        print(
            f"  {len(pre_undeliverable)} package(s) marked undeliverable during validation."
        )

    if not vehicles:
        print("ERROR: No valid vehicles available — cannot plan routes.", file=sys.stderr)
        # Still write empty output files so the caller always has them.
        all_undeliverable = dict(pre_undeliverable)
        write_stops_order({}, distances, args.output)
        write_summary({}, vehicles, distances, args.output)
        write_undeliverable(all_undeliverable, args.output)
        total = len(packages) + len(pre_undeliverable)
        print(
            f"\nDone. Packages processed: {total}, delivered: 0, "
            f"undeliverable: {len(all_undeliverable)}"
        )
        return

    print("Assigning packages to vehicles …")
    routes, assignment_undeliverable = assign_packages(packages, vehicles, distances)

    assigned_count = sum(len(r.stops) for r in routes.values())
    print(
        f"  {assigned_count} package(s) assigned, "
        f"{len(assignment_undeliverable)} undeliverable during assignment."
    )

    print("Optimising routes …")
    routes = optimize_routes(routes, distances)

    print("Writing output files …")
    all_undeliverable = dict(pre_undeliverable)
    all_undeliverable.update(assignment_undeliverable)

    write_stops_order(routes, distances, args.output)
    write_summary(routes, vehicles, distances, args.output)
    write_undeliverable(all_undeliverable, args.output)

    total_processed = len(packages) + len(pre_undeliverable)
    total_delivered = sum(len(r.stops) for r in routes.values())
    total_undeliverable = len(all_undeliverable)

    print(
        f"\nDone. Packages processed: {total_processed}, "
        f"delivered: {total_delivered}, "
        f"undeliverable: {total_undeliverable}"
    )


if __name__ == "__main__":
    main()
