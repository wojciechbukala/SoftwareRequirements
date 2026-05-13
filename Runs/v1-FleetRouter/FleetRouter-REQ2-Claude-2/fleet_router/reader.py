import csv
import sys
from typing import Dict, List, Tuple

from .models import DistanceEntry, Location, Package, Vehicle


def parse_time(s: str) -> int:
    """Parse HH:MM string to minutes from midnight."""
    parts = s.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {s!r}")
    return int(parts[0]) * 60 + int(parts[1])


def read_locations(filepath: str) -> Dict[str, Location]:
    locations: Dict[str, Location] = {}
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            loc_id = row["location_id"].strip()
            locations[loc_id] = Location(id=loc_id, name=row["name"].strip())
    return locations


def read_vehicles(filepath: str) -> List[Vehicle]:
    vehicles: List[Vehicle] = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                vehicles.append(
                    Vehicle(
                        id=row["vehicle_id"].strip(),
                        max_weight_kg=float(row["max_weight_kg"]),
                        max_volume_m3=float(row["max_volume_m3"]),
                        depot_location_id=row["depot_location_id"].strip(),
                    )
                )
            except (ValueError, KeyError) as e:
                vid = row.get("vehicle_id", "?").strip()
                print(
                    f"Warning: skipping invalid vehicle row (id={vid}): {e}",
                    file=sys.stderr,
                )
    return vehicles


def read_packages(filepath: str) -> Tuple[List[Package], List[Tuple[str, str]]]:
    """Return (valid_packages, excluded_rows) where excluded_rows is (id, reason)."""
    packages: List[Package] = []
    excluded: List[Tuple[str, str]] = []

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pkg_id = row.get("package_id", "").strip()
            try:
                priority = int(row["priority"].strip())
                if priority not in (0, 1):
                    print(
                        f"Warning: package {pkg_id!r} has invalid priority value "
                        f"{priority!r}, excluding.",
                        file=sys.stderr,
                    )
                    excluded.append((pkg_id, "invalid_priority"))
                    continue

                packages.append(
                    Package(
                        id=pkg_id,
                        destination_id=row["destination_id"].strip(),
                        weight_kg=float(row["weight_kg"]),
                        volume_m3=float(row["volume_m3"]),
                        tw_open=parse_time(row["tw_open"]),
                        tw_close=parse_time(row["tw_close"]),
                        service_min=int(row["service_min"]),
                        priority=priority,
                    )
                )
            except (ValueError, KeyError) as e:
                print(
                    f"Warning: skipping invalid package row (id={pkg_id!r}): {e}",
                    file=sys.stderr,
                )
                excluded.append((pkg_id, str(e)))

    return packages, excluded


def read_distances(
    filepath: str,
) -> Dict[Tuple[str, str], DistanceEntry]:
    distances: Dict[Tuple[str, str], DistanceEntry] = {}
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            from_id = row["from_location_id"].strip()
            to_id = row["to_location_id"].strip()
            entry = DistanceEntry(
                from_id=from_id,
                to_id=to_id,
                distance_km=float(row["distance_km"]),
                travel_time_min=int(row["travel_time_min"]),
            )
            distances[(from_id, to_id)] = entry
    return distances
