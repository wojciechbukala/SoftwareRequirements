import csv
import os
import sys
from typing import Dict, List, Set, Tuple

from .models import DistanceMap, Location, Package, Vehicle, parse_time

REASON_TIME_WINDOW = "TIME_WINDOW"


def _read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_locations(path: str) -> Dict[str, Location]:
    rows = _read_csv(path)
    return {
        row["location_id"].strip(): Location(row["location_id"].strip(), row["name"].strip())
        for row in rows
    }


def read_vehicles(
    path: str, known_location_ids: Set[str]
) -> Tuple[List[Vehicle], List[str]]:
    rows = _read_csv(path)
    vehicles: List[Vehicle] = []
    errors: List[str] = []

    for row in rows:
        vid = row["vehicle_id"].strip()
        depot = row["depot_location_id"].strip()
        if depot not in known_location_ids:
            errors.append(
                f"Vehicle '{vid}' references unknown depot location '{depot}' — excluded."
            )
            continue
        vehicles.append(
            Vehicle(
                vehicle_id=vid,
                max_weight_kg=float(row["max_weight_kg"]),
                max_volume_m3=float(row["max_volume_m3"]),
                depot_location_id=depot,
            )
        )

    return vehicles, errors


def read_packages(
    path: str, known_location_ids: Set[str]
) -> Tuple[List[Package], List[Tuple[str, str]], List[str]]:
    """Return (valid_packages, pre_undeliverable_list, error_messages)."""
    rows = _read_csv(path)
    packages: List[Package] = []
    pre_undeliverable: List[Tuple[str, str]] = []
    errors: List[str] = []

    for row in rows:
        pid = row["package_id"].strip()
        dest = row["destination_id"].strip()

        if dest not in known_location_ids:
            errors.append(
                f"Package '{pid}' references unknown location '{dest}' — excluded."
            )
            continue

        raw_priority = row["priority"].strip()
        try:
            priority = int(raw_priority)
        except ValueError:
            errors.append(
                f"Package '{pid}' has non-integer priority '{raw_priority}' — excluded."
            )
            continue

        if priority not in (0, 1):
            errors.append(
                f"Package '{pid}' has priority {priority} (must be 0 or 1) — excluded."
            )
            continue

        tw_open = parse_time(row["tw_open"])
        tw_close = parse_time(row["tw_close"])

        if tw_close <= tw_open:
            pre_undeliverable.append((pid, REASON_TIME_WINDOW))
            continue

        packages.append(
            Package(
                package_id=pid,
                destination_id=dest,
                weight_kg=float(row["weight_kg"]),
                volume_m3=float(row["volume_m3"]),
                tw_open=tw_open,
                tw_close=tw_close,
                service_min=int(row["service_min"]),
                priority=priority,
            )
        )

    return packages, pre_undeliverable, errors


def read_distances(path: str) -> DistanceMap:
    rows = _read_csv(path)
    distances: DistanceMap = {}
    for row in rows:
        from_id = row["from_location_id"].strip()
        to_id = row["to_location_id"].strip()
        distances[(from_id, to_id)] = (
            float(row["distance_km"]),
            int(row["travel_time_min"]),
        )
    return distances


def read_all(
    input_dir: str,
) -> Tuple[
    List[Package],
    List[Vehicle],
    Dict[str, Location],
    DistanceMap,
    List[Tuple[str, str]],
    List[str],
]:
    """Read and perform basic validation on all four input files.

    Terminates with an error message if any required file is absent.
    Returns (packages, vehicles, locations, distances, pre_undeliverable, warnings).
    """
    required = ["packages.csv", "vehicles.csv", "locations.csv", "distances.csv"]
    for fname in required:
        fpath = os.path.join(input_dir, fname)
        if not os.path.isfile(fpath):
            print(f"ERROR: Required input file is missing: {fpath}", file=sys.stderr)
            sys.exit(1)

    locations = read_locations(os.path.join(input_dir, "locations.csv"))
    known_ids = set(locations.keys())

    vehicles, vehicle_errors = read_vehicles(
        os.path.join(input_dir, "vehicles.csv"), known_ids
    )
    packages, pre_undeliverable, package_errors = read_packages(
        os.path.join(input_dir, "packages.csv"), known_ids
    )
    distances = read_distances(os.path.join(input_dir, "distances.csv"))

    warnings = vehicle_errors + package_errors
    return packages, vehicles, locations, distances, pre_undeliverable, warnings
