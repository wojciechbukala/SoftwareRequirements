"""
Checks whether packages are inherently undeliverable regardless of routing decisions,
following the Alloy model predicates exactly.
"""
from typing import Dict, Tuple

from models import Package, Vehicle

REASON_NO_VEHICLE = "NO_VEHICLE"
REASON_UNREACHABLE = "UNREACHABLE"
REASON_CAPACITY_WEIGHT = "CAPACITY_WEIGHT"
REASON_CAPACITY_VOLUME = "CAPACITY_VOLUME"
REASON_TIME_WINDOW = "TIME_WINDOW"
REASON_MAX_DRIVER_TIME = "MAX_DRIVER_TIME"


def travel_time(from_id: str, to_id: str, distances: Dict) -> int | None:
    if from_id == to_id:
        return 0
    entry = distances.get((from_id, to_id))
    return entry[1] if entry is not None else None


def distance_km(from_id: str, to_id: str, distances: Dict) -> float | None:
    if from_id == to_id:
        return 0.0
    entry = distances.get((from_id, to_id))
    return entry[0] if entry is not None else None


def _deserves_unreachable(pkg: Package, vehicles: Dict[str, Vehicle], distances: Dict) -> bool:
    """True if no vehicle can reach destination and return to its depot."""
    return all(
        travel_time(v.depot_location_id, pkg.destination_id, distances) is None
        or travel_time(pkg.destination_id, v.depot_location_id, distances) is None
        for v in vehicles.values()
    )


def _deserves_capacity_weight(pkg: Package, vehicles: Dict[str, Vehicle]) -> bool:
    return all(pkg.weight_kg > v.max_weight_kg for v in vehicles.values())


def _deserves_capacity_volume(pkg: Package, vehicles: Dict[str, Vehicle]) -> bool:
    return all(pkg.volume_m3 > v.max_volume_m3 for v in vehicles.values())


def _deserves_time_window(pkg: Package, vehicles: Dict[str, Vehicle], distances: Dict) -> bool:
    """True if earliest possible arrival exceeds tw_close for every vehicle."""
    for v in vehicles.values():
        t = travel_time(v.depot_location_id, pkg.destination_id, distances)
        if t is not None and t <= pkg.tw_close:
            return False
    return True


def _deserves_max_driver_time(pkg: Package, vehicles: Dict[str, Vehicle], distances: Dict) -> bool:
    """True if minimum round-trip time (outbound + service + inbound) exceeds 480 for all vehicles."""
    for v in vehicles.values():
        outbound = travel_time(v.depot_location_id, pkg.destination_id, distances)
        inbound = travel_time(pkg.destination_id, v.depot_location_id, distances)
        if outbound is not None and inbound is not None:
            if outbound + pkg.service_min + inbound <= 480:
                return False
    return True


def find_inherently_undeliverable(
    packages: Dict[str, Package],
    vehicles: Dict[str, Vehicle],
    distances: Dict,
) -> Dict[str, str]:
    """
    Returns {package_id: reason_code} for packages that cannot be delivered
    by any vehicle regardless of route construction.

    Reason codes follow the priority order defined in the Alloy model.
    """
    undeliverable = {}
    vehicle_list = list(vehicles.values())

    for pkg_id, pkg in packages.items():
        if not vehicle_list:
            undeliverable[pkg_id] = REASON_NO_VEHICLE
            continue

        if _deserves_unreachable(pkg, vehicles, distances):
            undeliverable[pkg_id] = REASON_UNREACHABLE
            continue

        if _deserves_capacity_weight(pkg, vehicles):
            undeliverable[pkg_id] = REASON_CAPACITY_WEIGHT
            continue

        if _deserves_capacity_volume(pkg, vehicles):
            undeliverable[pkg_id] = REASON_CAPACITY_VOLUME
            continue

        if _deserves_time_window(pkg, vehicles, distances):
            undeliverable[pkg_id] = REASON_TIME_WINDOW
            continue

        if _deserves_max_driver_time(pkg, vehicles, distances):
            undeliverable[pkg_id] = REASON_MAX_DRIVER_TIME
            continue

    return undeliverable
