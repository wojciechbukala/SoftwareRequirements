"""Input file reading and validation for FleetRouter."""

import csv
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

from .models import Location, Package, Vehicle, time_to_minutes


Distances = Dict[Tuple[str, str], Tuple[float, int]]  # (from, to) -> (km, min)


def _open_csv(path: Path) -> List[dict]:
    """Read a CSV file and return list of row dicts."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_locations(input_dir: Path) -> Dict[str, Location]:
    """Load and return locations keyed by location_id."""
    path = input_dir / "locations.csv"
    if not path.exists():
        print(f"ERROR: Missing required input file: {path}", file=sys.stderr)
        sys.exit(1)

    locations = {}
    for row in _open_csv(path):
        loc_id = row["location_id"].strip()
        locations[loc_id] = Location(location_id=loc_id, name=row["name"].strip())
    return locations


def load_distances(input_dir: Path, locations: Dict[str, Location]) -> Distances:
    """Load distances and report gaps for unknown location references."""
    path = input_dir / "distances.csv"
    if not path.exists():
        print(f"ERROR: Missing required input file: {path}", file=sys.stderr)
        sys.exit(1)

    distances: Distances = {}
    for row in _open_csv(path):
        from_id = row["from_location_id"].strip()
        to_id = row["to_location_id"].strip()

        if from_id not in locations:
            print(
                f"WARNING: distances.csv references unknown location '{from_id}', skipping row.",
                file=sys.stderr,
            )
            continue
        if to_id not in locations:
            print(
                f"WARNING: distances.csv references unknown location '{to_id}', skipping row.",
                file=sys.stderr,
            )
            continue

        dist_km = float(row["distance_km"])
        travel_min = int(row["travel_time_min"])
        distances[(from_id, to_id)] = (dist_km, travel_min)

    return distances


def load_vehicles(
    input_dir: Path, locations: Dict[str, Location]
) -> List[Vehicle]:
    """Load vehicles, excluding those with unknown depot location IDs."""
    path = input_dir / "vehicles.csv"
    if not path.exists():
        print(f"ERROR: Missing required input file: {path}", file=sys.stderr)
        sys.exit(1)

    vehicles = []
    for row in _open_csv(path):
        depot_id = row["depot_location_id"].strip()
        vehicle_id = row["vehicle_id"].strip()

        if depot_id not in locations:
            print(
                f"WARNING: Vehicle '{vehicle_id}' references unknown depot location "
                f"'{depot_id}'; excluding from processing.",
                file=sys.stderr,
            )
            continue

        vehicles.append(
            Vehicle(
                vehicle_id=vehicle_id,
                max_weight_kg=float(row["max_weight_kg"]),
                max_volume_m3=float(row["max_volume_m3"]),
                depot_location_id=depot_id,
            )
        )

    return vehicles


def load_packages(
    input_dir: Path,
    locations: Dict[str, Location],
) -> Tuple[List[Package], List[Tuple[str, str]]]:
    """
    Load packages, performing validation.

    Returns:
        valid_packages: packages that passed all input validation
        pre_undeliverable: [(package_id, reason)] for packages with invalid time windows
    """
    path = input_dir / "packages.csv"
    if not path.exists():
        print(f"ERROR: Missing required input file: {path}", file=sys.stderr)
        sys.exit(1)

    valid_packages: List[Package] = []
    pre_undeliverable: List[Tuple[str, str]] = []

    for row in _open_csv(path):
        pkg_id = row["package_id"].strip()
        dest_id = row["destination_id"].strip()

        # Validate destination location
        if dest_id not in locations:
            print(
                f"WARNING: Package '{pkg_id}' references unknown destination location "
                f"'{dest_id}'; excluding from processing.",
                file=sys.stderr,
            )
            continue

        # Validate priority value
        priority_str = row["priority"].strip()
        if priority_str not in ("0", "1"):
            print(
                f"WARNING: Package '{pkg_id}' has invalid priority value '{priority_str}' "
                f"(must be 0 or 1); excluding from processing.",
                file=sys.stderr,
            )
            continue

        tw_open = time_to_minutes(row["tw_open"])
        tw_close = time_to_minutes(row["tw_close"])

        # Validate time window
        if tw_close <= tw_open:
            pre_undeliverable.append((pkg_id, "TIME_WINDOW"))
            continue

        valid_packages.append(
            Package(
                package_id=pkg_id,
                destination_id=dest_id,
                weight_kg=float(row["weight_kg"]),
                volume_m3=float(row["volume_m3"]),
                tw_open=tw_open,
                tw_close=tw_close,
                service_min=int(row["service_min"]),
                priority=int(priority_str),
            )
        )

    return valid_packages, pre_undeliverable


def load_all(
    input_dir: Path,
) -> Tuple[
    Dict[str, Location],
    Distances,
    List[Vehicle],
    List[Package],
    List[Tuple[str, str]],
]:
    """Load and validate all input files. Returns (locations, distances, vehicles, packages, pre_undeliverable)."""
    input_dir = Path(input_dir)

    for fname in ("locations.csv", "distances.csv", "vehicles.csv", "packages.csv"):
        if not (input_dir / fname).exists():
            print(f"ERROR: Missing required input file: {input_dir / fname}", file=sys.stderr)
            sys.exit(1)

    locations = load_locations(input_dir)
    distances = load_distances(input_dir, locations)
    vehicles = load_vehicles(input_dir, locations)
    packages, pre_undeliverable = load_packages(input_dir, locations)

    return locations, distances, vehicles, packages, pre_undeliverable
