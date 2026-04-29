import csv
import os
import sys
from models import Package, Vehicle, Location


def parse_time(time_str: str) -> int:
    """Parse HH:MM string to minutes from midnight."""
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {time_str!r}")
    return int(parts[0]) * 60 + int(parts[1])


def read_locations(filepath: str) -> dict:
    locations = {}
    with open(filepath, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            loc_id = row["location_id"].strip()
            locations[loc_id] = Location(location_id=loc_id, name=row["name"].strip())
    return locations


def read_vehicles(filepath: str, locations: dict) -> tuple:
    vehicles = []
    excluded = []
    with open(filepath, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            vid = row["vehicle_id"].strip()
            depot_id = row["depot_location_id"].strip()
            if depot_id not in locations:
                print(
                    f"Warning: vehicle {vid!r} references unknown location {depot_id!r} — excluded.",
                    file=sys.stderr,
                )
                excluded.append(vid)
                continue
            vehicles.append(
                Vehicle(
                    vehicle_id=vid,
                    max_weight_kg=float(row["max_weight_kg"]),
                    max_volume_m3=float(row["max_volume_m3"]),
                    depot_location_id=depot_id,
                )
            )
    return vehicles, excluded


def read_packages(filepath: str, locations: dict) -> tuple:
    """Return (valid_packages, excluded_ids, validation_undeliverable)."""
    valid = []
    excluded_ids = []
    validation_undeliverable = []  # list of (package_id, reason)

    with open(filepath, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            pid = row["package_id"].strip()
            dest_id = row["destination_id"].strip()

            if dest_id not in locations:
                print(
                    f"Warning: package {pid!r} references unknown location {dest_id!r} — excluded.",
                    file=sys.stderr,
                )
                excluded_ids.append(pid)
                continue

            try:
                priority = int(row["priority"].strip())
            except ValueError:
                print(
                    f"Warning: package {pid!r} has non-integer priority — excluded.",
                    file=sys.stderr,
                )
                excluded_ids.append(pid)
                continue

            if priority not in (0, 1):
                print(
                    f"Warning: package {pid!r} has invalid priority {priority!r} — excluded.",
                    file=sys.stderr,
                )
                excluded_ids.append(pid)
                continue

            try:
                tw_open = parse_time(row["tw_open"])
                tw_close = parse_time(row["tw_close"])
            except (ValueError, KeyError) as exc:
                print(
                    f"Warning: package {pid!r} has unparseable time window ({exc}) — excluded.",
                    file=sys.stderr,
                )
                excluded_ids.append(pid)
                continue

            if tw_close <= tw_open:
                print(
                    f"Warning: package {pid!r} has invalid time window "
                    f"({row['tw_open']} >= {row['tw_close']}) — undeliverable.",
                    file=sys.stderr,
                )
                validation_undeliverable.append((pid, "TIME_WINDOW"))
                continue

            valid.append(
                Package(
                    package_id=pid,
                    destination_id=dest_id,
                    weight_kg=float(row["weight_kg"]),
                    volume_m3=float(row["volume_m3"]),
                    tw_open=tw_open,
                    tw_close=tw_close,
                    service_min=int(row["service_min"]),
                    priority=priority,
                )
            )

    return valid, excluded_ids, validation_undeliverable


def read_distances(filepath: str) -> dict:
    """Return dict mapping (from_id, to_id) -> (distance_km, travel_time_min)."""
    distances = {}
    with open(filepath, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            from_id = row["from_location_id"].strip()
            to_id = row["to_location_id"].strip()
            distances[(from_id, to_id)] = (
                float(row["distance_km"]),
                float(row["travel_time_min"]),
            )
    return distances


def load_inputs(input_dir: str) -> tuple:
    """
    Load and validate all input files.
    Returns (locations, vehicles, packages, distances, validation_undeliverable).
    Exits with an error message if any required file is missing.
    """
    required = {
        "locations.csv": "locations",
        "vehicles.csv": "vehicles",
        "packages.csv": "packages",
        "distances.csv": "distances",
    }
    for filename in required:
        path = os.path.join(input_dir, filename)
        if not os.path.isfile(path):
            print(
                f"Error: required input file '{filename}' not found in {input_dir!r}.",
                file=sys.stderr,
            )
            sys.exit(1)

    locations = read_locations(os.path.join(input_dir, "locations.csv"))
    vehicles, _ = read_vehicles(os.path.join(input_dir, "vehicles.csv"), locations)
    packages, _, validation_undeliverable = read_packages(
        os.path.join(input_dir, "packages.csv"), locations
    )
    distances = read_distances(os.path.join(input_dir, "distances.csv"))

    return locations, vehicles, packages, distances, validation_undeliverable
