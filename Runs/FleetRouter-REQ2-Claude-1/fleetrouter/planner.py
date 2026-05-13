from typing import Dict, List, Optional, Tuple

from .models import (
    Package,
    Vehicle,
    VehicleRoute,
    RouteStop,
    START_TIME_MIN,
    MAX_DRIVER_TIME_MIN,
)

DistanceMap = Dict[Tuple[str, str], Tuple[float, int]]
PackageMap = Dict[str, Package]

# Lower number = higher priority when reporting undeliverable reason
_REASON_PRIORITY: Dict[str, int] = {
    "UNREACHABLE": 1,
    "TIME_WINDOW": 2,
    "MAX_DRIVER_TIME": 3,
    "CAPACITY_WEIGHT": 4,
    "CAPACITY_VOLUME": 5,
    "NO_VEHICLE": 6,
}


def _better_reason(current: str, candidate: str) -> str:
    if _REASON_PRIORITY.get(candidate, 99) < _REASON_PRIORITY.get(current, 99):
        return candidate
    return current


def compute_route(
    depot_id: str,
    sequence: List[str],
    pkg_map: PackageMap,
    distances: DistanceMap,
) -> Tuple[bool, List[dict], float, int]:
    """
    Simulate a route and return timing data.
    Returns (feasible, stops_data, total_distance_km, total_time_min).
    stops_data entries: {location_id, package_id, arrival, departure}.
    """
    current_time = START_TIME_MIN
    current_loc = depot_id
    total_dist = 0.0
    stops_data: List[dict] = []

    for pkg_id in sequence:
        pkg = pkg_map[pkg_id]
        dest = pkg.destination_id
        key = (current_loc, dest)

        if key not in distances:
            return False, [], 0.0, 0

        dist_km, travel_min = distances[key]
        arrival = current_time + travel_min

        if arrival > pkg.tw_close:
            return False, [], 0.0, 0

        departure = max(arrival, pkg.tw_open) + pkg.service_min
        total_dist += dist_km
        stops_data.append(
            {
                "location_id": dest,
                "package_id": pkg_id,
                "arrival": arrival,
                "departure": departure,
            }
        )
        current_time = departure
        current_loc = dest

    if sequence:
        ret_key = (current_loc, depot_id)
        if ret_key not in distances:
            return False, [], 0.0, 0
        dist_km, travel_min = distances[ret_key]
        total_dist += dist_km
        end_time = current_time + travel_min
    else:
        end_time = START_TIME_MIN

    total_time = end_time - START_TIME_MIN
    if total_time > MAX_DRIVER_TIME_MIN:
        return False, [], 0.0, 0

    return True, stops_data, total_dist, total_time


def _route_failure_reason(
    depot_id: str,
    sequence: List[str],
    pkg_map: PackageMap,
    distances: DistanceMap,
) -> Optional[str]:
    """Return why this route sequence is infeasible, or None if feasible."""
    current_time = START_TIME_MIN
    current_loc = depot_id

    for pkg_id in sequence:
        pkg = pkg_map[pkg_id]
        dest = pkg.destination_id
        key = (current_loc, dest)

        if key not in distances:
            return "UNREACHABLE"

        _, travel_min = distances[key]
        arrival = current_time + travel_min

        if arrival > pkg.tw_close:
            return "TIME_WINDOW"

        departure = max(arrival, pkg.tw_open) + pkg.service_min
        current_time = departure
        current_loc = dest

    if sequence:
        ret_key = (current_loc, depot_id)
        if ret_key not in distances:
            return "UNREACHABLE"
        _, travel_min = distances[ret_key]
        if current_time + travel_min - START_TIME_MIN > MAX_DRIVER_TIME_MIN:
            return "MAX_DRIVER_TIME"

    return None


def _find_best_insertion(
    vehicle: Vehicle,
    current_seq: List[str],
    pkg: Package,
    pkg_map: PackageMap,
    distances: DistanceMap,
    current_weight: float,
    current_volume: float,
) -> Tuple[Optional[int], float, int]:
    """
    Find the best position to insert pkg into vehicle's route.
    Returns (best_position, best_total_distance, best_total_time),
    or (None, inf, inf) if no feasible insertion exists.
    """
    if current_weight + pkg.weight_kg > vehicle.max_weight_kg + 1e-9:
        return None, float("inf"), float("inf")
    if current_volume + pkg.volume_m3 > vehicle.max_volume_m3 + 1e-9:
        return None, float("inf"), float("inf")

    best_pos: Optional[int] = None
    best_dist = float("inf")
    best_time_val = float("inf")

    for pos in range(len(current_seq) + 1):
        new_seq = current_seq[:pos] + [pkg.package_id] + current_seq[pos:]
        ok, _, dist, time_val = compute_route(
            vehicle.depot_location_id, new_seq, pkg_map, distances
        )
        if ok:
            if dist < best_dist or (dist == best_dist and time_val < best_time_val):
                best_dist = dist
                best_time_val = time_val
                best_pos = pos

    return best_pos, best_dist, best_time_val


def _get_vehicle_failure_reason(
    vehicle: Vehicle,
    current_seq: List[str],
    pkg: Package,
    pkg_map: PackageMap,
    distances: DistanceMap,
    current_weight: float,
    current_volume: float,
) -> str:
    """Determine the best (most specific) reason this vehicle cannot accept the package."""
    if current_weight + pkg.weight_kg > vehicle.max_weight_kg + 1e-9:
        return "CAPACITY_WEIGHT"
    if current_volume + pkg.volume_m3 > vehicle.max_volume_m3 + 1e-9:
        return "CAPACITY_VOLUME"

    # Return path must exist regardless of insertion position
    if (pkg.destination_id, vehicle.depot_location_id) not in distances:
        return "UNREACHABLE"

    best_reason = "NO_VEHICLE"
    for pos in range(len(current_seq) + 1):
        new_seq = current_seq[:pos] + [pkg.package_id] + current_seq[pos:]
        reason = _route_failure_reason(
            vehicle.depot_location_id, new_seq, pkg_map, distances
        )
        if reason is not None:
            best_reason = _better_reason(best_reason, reason)

    return best_reason


def _two_opt(
    depot_id: str,
    sequence: List[str],
    pkg_map: PackageMap,
    distances: DistanceMap,
) -> List[str]:
    """Improve a route using 2-opt local search (first-improvement strategy)."""
    if len(sequence) < 2:
        return sequence

    best = list(sequence)
    _, _, best_dist, best_time = compute_route(depot_id, best, pkg_map, distances)

    improved = True
    while improved:
        improved = False
        n = len(best)
        for i in range(n - 1):
            for j in range(i + 2, n):
                new_seq = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                ok, _, dist, time_val = compute_route(
                    depot_id, new_seq, pkg_map, distances
                )
                if ok and (
                    dist < best_dist - 1e-9
                    or (abs(dist - best_dist) < 1e-9 and time_val < best_time)
                ):
                    best = new_seq
                    best_dist = dist
                    best_time = time_val
                    improved = True
                    break
            if improved:
                break

    return best


def plan_routes(
    packages: List[Package],
    vehicles: List[Vehicle],
    locations: dict,
    distances: DistanceMap,
) -> Tuple[List[VehicleRoute], List[Tuple[str, str]]]:
    """
    Assign packages to vehicles and build optimized routes.
    Returns (routes, undeliverable_list) where undeliverable_list is
    [(package_id, reason_code)].
    """
    pkg_map: PackageMap = {p.package_id: p for p in packages}

    vehicle_seqs: Dict[str, List[str]] = {v.vehicle_id: [] for v in vehicles}
    vehicle_weight: Dict[str, float] = {v.vehicle_id: 0.0 for v in vehicles}
    vehicle_volume: Dict[str, float] = {v.vehicle_id: 0.0 for v in vehicles}

    undeliverable: List[Tuple[str, str]] = []

    # Priority packages first, then earlier time windows first
    sorted_pkgs = sorted(packages, key=lambda p: (-p.priority, p.tw_open))

    for pkg in sorted_pkgs:
        best_vehicle_id: Optional[str] = None
        best_pos: Optional[int] = None
        best_dist = float("inf")
        best_time_val = float("inf")
        worst_reason = "NO_VEHICLE"

        for vehicle in vehicles:
            v_id = vehicle.vehicle_id
            seq = vehicle_seqs[v_id]
            w = vehicle_weight[v_id]
            vol = vehicle_volume[v_id]

            pos, dist, time_val = _find_best_insertion(
                vehicle, seq, pkg, pkg_map, distances, w, vol
            )

            if pos is not None:
                if dist < best_dist or (dist == best_dist and time_val < best_time_val):
                    best_dist = dist
                    best_time_val = time_val
                    best_pos = pos
                    best_vehicle_id = v_id
            else:
                reason = _get_vehicle_failure_reason(
                    vehicle, seq, pkg, pkg_map, distances, w, vol
                )
                worst_reason = _better_reason(worst_reason, reason)

        if best_vehicle_id is not None:
            seq = vehicle_seqs[best_vehicle_id]
            vehicle_seqs[best_vehicle_id] = (
                seq[:best_pos] + [pkg.package_id] + seq[best_pos:]
            )
            vehicle_weight[best_vehicle_id] += pkg.weight_kg
            vehicle_volume[best_vehicle_id] += pkg.volume_m3
        else:
            undeliverable.append((pkg.package_id, worst_reason))

    # Optimize each vehicle's route with 2-opt
    for vehicle in vehicles:
        v_id = vehicle.vehicle_id
        if vehicle_seqs[v_id]:
            vehicle_seqs[v_id] = _two_opt(
                vehicle.depot_location_id,
                vehicle_seqs[v_id],
                pkg_map,
                distances,
            )

    # Build final VehicleRoute objects
    routes: List[VehicleRoute] = []
    for vehicle in vehicles:
        v_id = vehicle.vehicle_id
        seq = vehicle_seqs[v_id]

        if seq:
            _, stops_data, total_dist, total_time = compute_route(
                vehicle.depot_location_id, seq, pkg_map, distances
            )
        else:
            stops_data = []
            total_dist = 0.0
            total_time = 0

        stops = [
            RouteStop(
                stop_position=i + 1,
                location_id=s["location_id"],
                package_id=s["package_id"],
                arrival_time=s["arrival"],
                departure_time=s["departure"],
            )
            for i, s in enumerate(stops_data)
        ]

        routes.append(
            VehicleRoute(
                vehicle=vehicle,
                package_sequence=seq,
                stops=stops,
                total_distance_km=total_dist,
                total_time_min=total_time,
                total_weight_kg=vehicle_weight[v_id],
                total_volume_m3=vehicle_volume[v_id],
            )
        )

    return routes, undeliverable
