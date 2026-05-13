import csv
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from .models import Package, Vehicle, Location, hhmm_to_minutes

DistanceMap = Dict[Tuple[str, str], Tuple[float, int]]


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def read_locations(path: Path) -> Dict[str, Location]:
    rows = _read_csv_rows(path)
    result: Dict[str, Location] = {}
    for row in rows:
        loc_id = row["location_id"].strip()
        name = row["name"].strip()
        result[loc_id] = Location(location_id=loc_id, name=name)
    return result


def read_distances(path: Path) -> DistanceMap:
    rows = _read_csv_rows(path)
    result: DistanceMap = {}
    for row in rows:
        from_id = row["from_location_id"].strip()
        to_id = row["to_location_id"].strip()
        dist_km = float(row["distance_km"])
        travel_min = int(row["travel_time_min"])
        result[(from_id, to_id)] = (dist_km, travel_min)
    return result


def read_vehicles(
    path: Path,
    locations: Dict[str, Location],
) -> Tuple[List[Vehicle], List[str]]:
    rows = _read_csv_rows(path)
    vehicles: List[Vehicle] = []
    warnings: List[str] = []

    for row in rows:
        v_id = row["vehicle_id"].strip()
        depot = row["depot_location_id"].strip()

        if depot not in locations:
            warnings.append(
                f"Vehicle '{v_id}' references unknown location '{depot}', excluded."
            )
            continue

        vehicles.append(
            Vehicle(
                vehicle_id=v_id,
                max_weight_kg=float(row["max_weight_kg"]),
                max_volume_m3=float(row["max_volume_m3"]),
                depot_location_id=depot,
            )
        )

    return vehicles, warnings


def read_packages(
    path: Path,
    locations: Dict[str, Location],
) -> Tuple[List[Package], List[Tuple[str, str]], List[str]]:
    """
    Returns (valid_packages, pre_validation_undeliverable, warnings).
    pre_validation_undeliverable: [(package_id, reason_code)] for packages
    that fail structural validation before routing (e.g. bad time window).
    """
    rows = _read_csv_rows(path)
    packages: List[Package] = []
    undeliverable: List[Tuple[str, str]] = []
    warnings: List[str] = []

    for row in rows:
        p_id = row["package_id"].strip()

        dest = row["destination_id"].strip()
        if dest not in locations:
            warnings.append(
                f"Package '{p_id}' references unknown location '{dest}', excluded."
            )
            continue

        try:
            priority = int(row["priority"].strip())
        except ValueError:
            warnings.append(
                f"Package '{p_id}' has non-integer priority value, excluded."
            )
            continue

        if priority not in (0, 1):
            warnings.append(
                f"Package '{p_id}' has invalid priority {priority} (must be 0 or 1), excluded."
            )
            continue

        try:
            tw_open = hhmm_to_minutes(row["tw_open"].strip())
            tw_close = hhmm_to_minutes(row["tw_close"].strip())
        except (ValueError, IndexError):
            warnings.append(
                f"Package '{p_id}' has invalid time window format, excluded."
            )
            continue

        if tw_close <= tw_open:
            undeliverable.append((p_id, "TIME_WINDOW"))
            continue

        try:
            weight_kg = float(row["weight_kg"])
            volume_m3 = float(row["volume_m3"])
            service_min = int(row["service_min"])
        except (ValueError, KeyError) as exc:
            warnings.append(
                f"Package '{p_id}' has invalid numeric field ({exc}), excluded."
            )
            continue

        packages.append(
            Package(
                package_id=p_id,
                destination_id=dest,
                weight_kg=weight_kg,
                volume_m3=volume_m3,
                tw_open=tw_open,
                tw_close=tw_close,
                service_min=service_min,
                priority=priority,
            )
        )

    return packages, undeliverable, warnings
