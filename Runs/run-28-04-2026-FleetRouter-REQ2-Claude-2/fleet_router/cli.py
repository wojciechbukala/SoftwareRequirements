import argparse
import os
import sys

from .planner import assign_packages, build_routes
from .reader import read_distances, read_locations, read_packages, read_vehicles
from .validator import validate_location_references, validate_time_windows
from .writer import write_stops_order, write_summary, write_undeliverable


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="fleetrouter",
        description="FleetRouter — daily route planning for courier companies.",
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="<dir>",
        help="Directory containing packages.csv, vehicles.csv, locations.csv, distances.csv",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="<dir>",
        help="Directory where stops_order.csv, summary.csv, undeliverable.csv will be written",
    )
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    required_files = ["packages.csv", "vehicles.csv", "locations.csv", "distances.csv"]
    for filename in required_files:
        path = os.path.join(input_dir, filename)
        if not os.path.isfile(path):
            print(f"Error: required input file not found: {path}", file=sys.stderr)
            return 1

    print("Reading input data...")
    try:
        locations = read_locations(os.path.join(input_dir, "locations.csv"))
        vehicles = read_vehicles(os.path.join(input_dir, "vehicles.csv"))
        packages, _ = read_packages(os.path.join(input_dir, "packages.csv"))
        distances = read_distances(os.path.join(input_dir, "distances.csv"))
    except OSError as e:
        print(f"Error reading input data: {e}", file=sys.stderr)
        return 1

    print("Validating input data...")
    packages, vehicles = validate_location_references(packages, vehicles, locations)
    packages, tw_undeliverable = validate_time_windows(packages)

    total_input_packages = len(packages) + len(tw_undeliverable)

    print("Assigning packages to vehicles...")
    vehicle_states, assignment_undeliverable = assign_packages(
        packages, vehicles, distances
    )

    all_undeliverable = tw_undeliverable + assignment_undeliverable

    print("Building and optimizing routes...")
    routes = build_routes(vehicle_states, vehicles, distances)

    os.makedirs(output_dir, exist_ok=True)

    print("Writing output files...")
    write_stops_order(routes, os.path.join(output_dir, "stops_order.csv"))
    write_summary(routes, os.path.join(output_dir, "summary.csv"))
    write_undeliverable(all_undeliverable, os.path.join(output_dir, "undeliverable.csv"))

    delivered = sum(len(r.stops) for r in routes)
    total_undeliverable = len(all_undeliverable)
    total_processed = total_input_packages

    print(
        f"Done. Packages processed: {total_processed}, "
        f"delivered: {delivered}, "
        f"undeliverable: {total_undeliverable}."
    )
    return 0
