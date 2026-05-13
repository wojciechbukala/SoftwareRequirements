import csv
import os
import sys
from typing import Dict, List, Set, Tuple

from .models import (
    DistanceEntry,
    DistanceMap,
    Location,
    Package,
    Vehicle,
    parse_time,
)


def _require_file(path: str) -> None:
    if not os.path.isfile(path):
        print(f"ERROR: Required input file not found: {path}", file=sys.stderr)
        sys.exit(1)


def read_locations(path: str) -> Dict[str, Location]:
    _require_file(path)
    locations: Dict[str, Location] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            loc_id = row["location_id"].strip()
            locations[loc_id] = Location(location_id=loc_id, name=row["name"].strip())
    return locations


def read_distances(path: str) -> DistanceMap:
    _require_file(path)
    dist_map: DistanceMap = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            from_id = row["from_location_id"].strip()
            to_id = row["to_location_id"].strip()
            entry = DistanceEntry(
                from_location_id=from_id,
                to_location_id=to_id,
                distance_km=float(row["distance_km"]),
                travel_time_min=int(row["travel_time_min"]),
            )
            dist_map[(from_id, to_id)] = entry
    return dist_map


def read_vehicles(path: str, known_locations: Set[str]) -> List[Vehicle]:
    _require_file(path)
    vehicles: List[Vehicle] = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            vid = row["vehicle_id"].strip()
            depot_id = row["depot_location_id"].strip()
            if depot_id not in known_locations:
                print(
                    f"WARNING: Vehicle '{vid}' references unknown location '{depot_id}'"
                    " — excluded from processing.",
                    file=sys.stderr,
                )
                continue
            vehicles.append(
                Vehicle(
                    vehicle_id=vid,
                    max_weight_kg=float(row["max_weight_kg"]),
                    max_volume_m3=float(row["max_volume_m3"]),
                    depot_location_id=depot_id,
                )
            )
    return vehicles


def read_packages(
    path: str, known_locations: Set[str]
) -> Tuple[List[Package], Dict[str, str]]:
    """
    Read and validate packages.csv.

    Returns (valid_packages, early_undeliverable) where early_undeliverable maps
    package_id -> reason for packages excluded before the planning phase.
    """
    _require_file(path)
    valid: List[Package] = []
    early_undeliverable: Dict[str, str] = {}

    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            pkg_id = row["package_id"].strip()
            dest_id = row["destination_id"].strip()

            if dest_id not in known_locations:
                print(
                    f"WARNING: Package '{pkg_id}' references unknown location"
                    f" '{dest_id}' — excluded from processing.",
                    file=sys.stderr,
                )
                continue

            priority_raw = row["priority"].strip()
            if priority_raw not in ("0", "1"):
                print(
                    f"WARNING: Package '{pkg_id}' has invalid priority value"
                    f" '{priority_raw}' — excluded from processing.",
                    file=sys.stderr,
                )
                continue

            tw_open = parse_time(row["tw_open"])
            tw_close = parse_time(row["tw_close"])
            if tw_close <= tw_open:
                early_undeliverable[pkg_id] = "TIME_WINDOW"
                continue

            valid.append(
                Package(
                    package_id=pkg_id,
                    destination_id=dest_id,
                    weight_kg=float(row["weight_kg"]),
                    volume_m3=float(row["volume_m3"]),
                    tw_open=tw_open,
                    tw_close=tw_close,
                    service_min=int(row["service_min"]),
                    priority=int(priority_raw),
                )
            )

    return valid, early_undeliverable
