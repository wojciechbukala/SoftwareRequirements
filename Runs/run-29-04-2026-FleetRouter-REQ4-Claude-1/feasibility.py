from typing import Dict, List, Optional, Tuple

from models import Package, Vehicle

MAX_DRIVER_MINUTES = 480  # 8 hours = 480 minutes since 08:00


def get_travel_time(distances: Dict, from_id: str, to_id: str) -> Optional[int]:
    if from_id == to_id:
        return 0
    entry = distances.get((from_id, to_id))
    return entry[1] if entry is not None else None


def get_distance_km(distances: Dict, from_id: str, to_id: str) -> Optional[float]:
    if from_id == to_id:
        return 0.0
    entry = distances.get((from_id, to_id))
    return entry[0] if entry is not None else None


def _is_reachable_via(vehicle: Vehicle, pkg: Package, distances: Dict) -> bool:
    out = get_travel_time(distances, vehicle.depot_location_id, pkg.destination_id)
    back = get_travel_time(distances, pkg.destination_id, vehicle.depot_location_id)
    return out is not None and back is not None


def _earliest_arrival(vehicle: Vehicle, pkg: Package, distances: Dict) -> Optional[int]:
    t = get_travel_time(distances, vehicle.depot_location_id, pkg.destination_id)
    return t  # departure from depot at minute 0


def classify_infeasible(pkg: Package, vehicles: List[Vehicle],
                        distances: Dict) -> Optional[str]:
    """
    Return a reason code if the package is inherently infeasible for ALL vehicles,
    or None if it may be deliverable.

    Priority order (most fundamental first):
      NO_VEHICLE → UNREACHABLE → CAPACITY_WEIGHT → CAPACITY_VOLUME
      → MAX_DRIVER_TIME → TIME_WINDOW
    """
    if not vehicles:
        return "NO_VEHICLE"

    any_reachable = False
    any_weight_ok = False
    any_volume_ok = False
    any_time_ok = False
    any_window_ok = False

    for v in vehicles:
        if not _is_reachable_via(v, pkg, distances):
            continue
        any_reachable = True

        if pkg.weight_kg <= v.max_weight_kg:
            any_weight_ok = True
        if pkg.volume_m3 <= v.max_volume_m3:
            any_volume_ok = True

        out = get_travel_time(distances, v.depot_location_id, pkg.destination_id)
        back = get_travel_time(distances, pkg.destination_id, v.depot_location_id)
        if out is not None and back is not None:
            if out + pkg.service_min + back <= MAX_DRIVER_MINUTES:
                any_time_ok = True
            earliest = out
            if earliest <= pkg.tw_close:
                any_window_ok = True

    if not any_reachable:
        return "UNREACHABLE"
    if not any_weight_ok:
        return "CAPACITY_WEIGHT"
    if not any_volume_ok:
        return "CAPACITY_VOLUME"
    if not any_time_ok:
        return "MAX_DRIVER_TIME"
    if not any_window_ok:
        return "TIME_WINDOW"

    return None


def check_all_packages(packages: List[Package], vehicles: List[Vehicle],
                       distances: Dict) -> Tuple[List[Package], Dict[str, str]]:
    """
    Split packages into feasible (may be routed) and infeasible (with reason).
    Returns (feasible_packages, undeliverable_dict).
    """
    feasible = []
    undeliverable = {}

    for pkg in packages:
        reason = classify_infeasible(pkg, vehicles, distances)
        if reason is not None:
            undeliverable[pkg.id] = reason
        else:
            feasible.append(pkg)

    return feasible, undeliverable
