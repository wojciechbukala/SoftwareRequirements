"""FleetRouter CLI entry point."""
import argparse
import os
import sys
from typing import Dict, List, Tuple

from .models import Package, Vehicle, Location
from .io import (read_locations, read_vehicles, read_packages, read_distances,
                 write_stops_order, write_undeliverable, write_summary)
from .router import plan_routes


def _validate_and_filter(packages: List[Package], vehicles: List[Vehicle],
                          locations: Dict, distances: dict,
                          undeliverable: List[Tuple[str, str]]) -> Tuple[List[Package], List[Vehicle]]:
    """
    Validate inputs and return filtered packages/vehicles.
    Appends to undeliverable list for bad packages.
    """
    valid_location_ids = set(locations.keys())

    # Filter vehicles with invalid depot location
    valid_vehicles = []
    for v in vehicles:
        if v.depot_id not in valid_location_ids:
            print(f"[WARN] Vehicle {v.id} references unknown location {v.depot_id}, excluded.",
                  file=sys.stderr)
        else:
            valid_vehicles.append(v)

    # Collect all reachable depots for UNREACHABLE check
    depot_ids = {v.depot_id for v in valid_vehicles}

    valid_packages = []
    for p in packages:
        # Check location exists
        if p.location_id not in valid_location_ids:
            print(f"[WARN] Package {p.id} references unknown location {p.location_id}, excluded.",
                  file=sys.stderr)
            continue

        # Validate time window
        if p.time_open >= p.time_close:
            undeliverable.append((p.id, 'TIME_WINDOW'))
            continue

        # Check UNREACHABLE: no depot can reach this package and return
        if valid_vehicles:
            reachable = False
            for depot in depot_ids:
                if ((depot, p.location_id) in distances and
                        (p.location_id, depot) in distances):
                    reachable = True
                    break
            if not reachable:
                undeliverable.append((p.id, 'UNREACHABLE'))
                continue

        valid_packages.append(p)

    return valid_packages, valid_vehicles


def main():
    parser = argparse.ArgumentParser(description='FleetRouter - daily route planner')
    parser.add_argument('--input', required=True, help='Input directory')
    parser.add_argument('--output', required=True, help='Output directory')
    args = parser.parse_args()

    in_dir = args.input
    out_dir = args.output
    os.makedirs(out_dir, exist_ok=True)

    # Read inputs
    locations = read_locations(os.path.join(in_dir, 'locations.csv'))
    vehicles = read_vehicles(os.path.join(in_dir, 'vehicles.csv'))
    packages = read_packages(os.path.join(in_dir, 'packages.csv'))
    distances = read_distances(os.path.join(in_dir, 'distances.csv'))

    undeliverable: List[Tuple[str, str]] = []

    # Validate and filter
    valid_packages, valid_vehicles = _validate_and_filter(
        packages, vehicles, locations, distances, undeliverable
    )

    if not valid_vehicles:
        print("[ERROR] No valid vehicles available.", file=sys.stderr)
        # All remaining packages are undeliverable
        for p in valid_packages:
            undeliverable.append((p.id, 'NO_VEHICLE'))
        valid_packages = []

    # Plan routes
    routes, new_undeliverable = plan_routes(valid_vehicles, valid_packages, distances)
    undeliverable.extend(new_undeliverable)

    # Only include routes that have at least one delivery stop
    active_routes = [r for r in routes if r.package_ids]

    # Write outputs
    write_stops_order(os.path.join(out_dir, 'stops_order.csv'), active_routes)
    write_undeliverable(os.path.join(out_dir, 'undeliverable.csv'), undeliverable)
    write_summary(os.path.join(out_dir, 'summary.csv'), active_routes)

    print(f"Done. {len(active_routes)} routes, {sum(len(r.package_ids) for r in active_routes)} packages delivered, "
          f"{len(undeliverable)} undeliverable.")


if __name__ == '__main__':
    main()
