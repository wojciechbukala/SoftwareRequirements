import argparse
import os
import sys

from .planner import plan_routes
from .reader import read_distances, read_locations, read_packages, read_vehicles
from .writer import (
    ensure_output_dir,
    write_stops_order,
    write_summary,
    write_undeliverable,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fleetrouter",
        description="Daily route planner for courier fleets.",
    )
    parser.add_argument(
        "--input", required=True, metavar="<dir>", help="Directory containing input CSV files"
    )
    parser.add_argument(
        "--output", required=True, metavar="<dir>", help="Directory for output CSV files"
    )
    args = parser.parse_args()

    in_dir: str = args.input
    out_dir: str = args.output

    if not os.path.isdir(in_dir):
        print(f"ERROR: Input directory does not exist: {in_dir}", file=sys.stderr)
        sys.exit(1)

    ensure_output_dir(out_dir)

    print("Reading and validating input data...")

    locations = read_locations(os.path.join(in_dir, "locations.csv"))
    dist_map = read_distances(os.path.join(in_dir, "distances.csv"))
    location_ids = set(locations.keys())
    vehicles = read_vehicles(os.path.join(in_dir, "vehicles.csv"), location_ids)
    packages, validation_undeliverable = read_packages(
        os.path.join(in_dir, "packages.csv"), location_ids
    )

    print(
        f"  Loaded {len(locations)} locations, {len(dist_map)} distance entries,"
        f" {len(vehicles)} vehicles, {len(packages)} valid packages."
    )
    if validation_undeliverable:
        print(
            f"  {len(validation_undeliverable)} package(s) excluded during validation."
        )

    if not vehicles:
        print("ERROR: No valid vehicles available — cannot plan routes.", file=sys.stderr)
        sys.exit(1)

    print("Planning routes...")
    assignments, planning_undeliverable = plan_routes(packages, vehicles, dist_map)

    all_undeliverable = {**validation_undeliverable, **planning_undeliverable}

    delivered_count = sum(len(pkgs) for pkgs in assignments.values())
    total_processed = len(packages) + len(validation_undeliverable)

    print("Writing output files...")
    write_stops_order(
        os.path.join(out_dir, "stops_order.csv"), vehicles, assignments, dist_map
    )
    write_summary(
        os.path.join(out_dir, "summary.csv"), vehicles, assignments, dist_map
    )
    write_undeliverable(
        os.path.join(out_dir, "undeliverable.csv"), all_undeliverable
    )

    print(
        f"\nPlanning complete: {total_processed} packages processed,"
        f" {delivered_count} delivered,"
        f" {len(all_undeliverable)} undeliverable."
    )


if __name__ == "__main__":
    main()
