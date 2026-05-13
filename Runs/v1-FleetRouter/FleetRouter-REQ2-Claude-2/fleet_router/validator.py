import sys
from typing import Dict, List, Tuple

from .models import Location, Package, Vehicle


def validate_location_references(
    packages: List[Package],
    vehicles: List[Vehicle],
    locations: Dict[str, Location],
) -> Tuple[List[Package], List[Vehicle]]:
    """Exclude packages and vehicles that reference unknown location IDs."""
    valid_packages: List[Package] = []
    for pkg in packages:
        if pkg.destination_id not in locations:
            print(
                f"Warning: package {pkg.id!r} references unknown location "
                f"{pkg.destination_id!r}, excluding.",
                file=sys.stderr,
            )
        else:
            valid_packages.append(pkg)

    valid_vehicles: List[Vehicle] = []
    for v in vehicles:
        if v.depot_location_id not in locations:
            print(
                f"Warning: vehicle {v.id!r} references unknown depot location "
                f"{v.depot_location_id!r}, excluding.",
                file=sys.stderr,
            )
        else:
            valid_vehicles.append(v)

    return valid_packages, valid_vehicles


def validate_time_windows(
    packages: List[Package],
) -> Tuple[List[Package], List[Tuple[str, str]]]:
    """Split packages into valid and those with invalid time windows."""
    valid: List[Package] = []
    undeliverable: List[Tuple[str, str]] = []

    for pkg in packages:
        if pkg.tw_close <= pkg.tw_open:
            undeliverable.append((pkg.id, "TIME_WINDOW"))
        else:
            valid.append(pkg)

    return valid, undeliverable
