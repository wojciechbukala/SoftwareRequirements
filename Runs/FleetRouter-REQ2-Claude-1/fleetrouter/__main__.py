import argparse
import sys
from pathlib import Path

from . import reader, planner, writer


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        prog="fleetrouter",
        description="FleetRouter: daily route planning for courier companies.",
    )
    arg_parser.add_argument(
        "--input",
        required=True,
        metavar="<dir>",
        help="Directory containing the four input CSV files.",
    )
    arg_parser.add_argument(
        "--output",
        required=True,
        metavar="<dir>",
        help="Directory where the three output CSV files will be written.",
    )
    args = arg_parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    required_inputs = {
        "locations.csv": input_dir / "locations.csv",
        "packages.csv": input_dir / "packages.csv",
        "vehicles.csv": input_dir / "vehicles.csv",
        "distances.csv": input_dir / "distances.csv",
    }
    for name, path in required_inputs.items():
        if not path.exists():
            print(f"Error: Required input file not found: {path}", file=sys.stderr)
            sys.exit(1)

    print("Reading input data...")
    locations = reader.read_locations(required_inputs["locations.csv"])
    distances = reader.read_distances(required_inputs["distances.csv"])

    vehicles, vehicle_warnings = reader.read_vehicles(
        required_inputs["vehicles.csv"], locations
    )
    packages, pre_undeliverable, package_warnings = reader.read_packages(
        required_inputs["packages.csv"], locations
    )

    for msg in vehicle_warnings + package_warnings:
        print(f"Warning: {msg}", file=sys.stderr)

    if not vehicles:
        print("Error: No valid vehicles found. Cannot plan routes.", file=sys.stderr)
        sys.exit(1)

    print("Planning and optimizing routes...")
    routes, planning_undeliverable = planner.plan_routes(
        packages, vehicles, locations, distances
    )

    all_undeliverable = pre_undeliverable + planning_undeliverable

    output_dir.mkdir(parents=True, exist_ok=True)
    print("Writing output files...")
    writer.write_stops_order(output_dir / "stops_order.csv", routes)
    writer.write_summary(output_dir / "summary.csv", routes, vehicles)
    writer.write_undeliverable(output_dir / "undeliverable.csv", all_undeliverable)

    total_processed = len(packages) + len(pre_undeliverable)
    delivered = sum(len(r.package_sequence) for r in routes)
    undeliverable_count = len(all_undeliverable)

    print(
        f"\nDone: {total_processed} packages processed | "
        f"{delivered} delivered | "
        f"{undeliverable_count} undeliverable."
    )


if __name__ == "__main__":
    main()
