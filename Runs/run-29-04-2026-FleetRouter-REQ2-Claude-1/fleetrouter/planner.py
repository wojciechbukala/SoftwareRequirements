from typing import Dict, List, Optional, Set, Tuple

from .models import (
    DistanceMap,
    Package,
    Vehicle,
    MAX_DRIVER_TIME_MIN,
    START_TIME_MIN,
)

# Lower value = higher reporting priority when package is undeliverable
_REASON_PRIORITY: Dict[str, int] = {
    "UNREACHABLE": 0,
    "CAPACITY_WEIGHT": 1,
    "CAPACITY_VOLUME": 2,
    "TIME_WINDOW": 3,
    "MAX_DRIVER_TIME": 4,
    "NO_VEHICLE": 5,
}

# (arrival_min, departure_min) per stop
StopTimes = List[Tuple[int, int]]
RouteResult = Tuple[StopTimes, float, int]  # (times, total_dist_km, total_time_min)


def simulate_route(
    vehicle: Vehicle,
    packages: List[Package],
    dist_map: DistanceMap,
) -> Tuple[Optional[RouteResult], Optional[str]]:
    """
    Simulate a vehicle route through packages in the given order.

    Returns (RouteResult, None) on success or (None, reason_code) on failure.
    All vehicles depart their depot at START_TIME_MIN (08:00).
    """
    if not packages:
        return ([], 0.0, 0), None

    current_loc = vehicle.depot_location_id
    current_time = START_TIME_MIN
    total_dist = 0.0
    times: StopTimes = []

    for pkg in packages:
        edge = (current_loc, pkg.destination_id)
        if current_loc == pkg.destination_id:
            arrival = current_time
        elif edge not in dist_map:
            return None, "UNREACHABLE"
        else:
            d = dist_map[edge]
            arrival = current_time + d.travel_time_min
            total_dist += d.distance_km
        service_start = max(arrival, pkg.tw_open)
        if service_start > pkg.tw_close:
            return None, "TIME_WINDOW"
        departure = service_start + pkg.service_min
        times.append((arrival, departure))
        current_loc = pkg.destination_id
        current_time = departure

    edge = (current_loc, vehicle.depot_location_id)
    if current_loc == vehicle.depot_location_id:
        return_travel_min = 0
    elif edge not in dist_map:
        return None, "UNREACHABLE"
    else:
        d = dist_map[edge]
        total_dist += d.distance_km
        return_travel_min = d.travel_time_min
    total_time = current_time + return_travel_min - START_TIME_MIN

    if total_time > MAX_DRIVER_TIME_MIN:
        return None, "MAX_DRIVER_TIME"

    return (times, total_dist, total_time), None


class _VehicleState:
    """Tracks a vehicle's partial route during the construction phase."""

    def __init__(self, vehicle: Vehicle) -> None:
        self.vehicle = vehicle
        self.packages: List[Package] = []
        self.total_weight = 0.0
        self.total_volume = 0.0
        self.route_distance = 0.0

    def within_weight(self, weight: float) -> bool:
        return self.total_weight + weight <= self.vehicle.max_weight_kg + 1e-9

    def within_volume(self, volume: float) -> bool:
        return self.total_volume + volume <= self.vehicle.max_volume_m3 + 1e-9

    def commit_insertion(self, pkg: Package, pos: int, new_dist: float) -> None:
        self.packages.insert(pos, pkg)
        self.total_weight += pkg.weight_kg
        self.total_volume += pkg.volume_m3
        self.route_distance = new_dist


def _select_reason(blocking: Set[str]) -> str:
    if not blocking:
        return "NO_VEHICLE"
    return min(blocking, key=lambda r: _REASON_PRIORITY[r])


def _two_opt(vehicle: Vehicle, packages: List[Package], dist_map: DistanceMap) -> List[Package]:
    """Improve route distance with 2-opt edge swaps."""
    if len(packages) <= 1:
        return packages

    best = packages[:]
    result, _ = simulate_route(vehicle, best, dist_map)
    if result is None:
        return best
    _, best_dist, best_time = result

    improved = True
    while improved:
        improved = False
        n = len(best)
        for i in range(n - 1):
            for j in range(i + 1, n):
                candidate = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                result, _ = simulate_route(vehicle, candidate, dist_map)
                if result is None:
                    continue
                _, cand_dist, cand_time = result
                if cand_dist < best_dist - 1e-9 or (
                    abs(cand_dist - best_dist) < 1e-9 and cand_time < best_time
                ):
                    best, best_dist, best_time = candidate, cand_dist, cand_time
                    improved = True
                    break
            if improved:
                break

    return best


def _or_opt(vehicle: Vehicle, packages: List[Package], dist_map: DistanceMap) -> List[Package]:
    """Improve route by relocating individual stops to cheaper positions."""
    if len(packages) <= 2:
        return packages

    best = packages[:]
    result, _ = simulate_route(vehicle, best, dist_map)
    if result is None:
        return best
    _, best_dist, best_time = result

    improved = True
    while improved:
        improved = False
        n = len(best)
        for i in range(n):
            pkg = best[i]
            remaining = best[:i] + best[i + 1 :]
            for j in range(len(remaining) + 1):
                if j == i:
                    continue
                candidate = remaining[:j] + [pkg] + remaining[j:]
                result, _ = simulate_route(vehicle, candidate, dist_map)
                if result is None:
                    continue
                _, cand_dist, cand_time = result
                if cand_dist < best_dist - 1e-9 or (
                    abs(cand_dist - best_dist) < 1e-9 and cand_time < best_time
                ):
                    best, best_dist, best_time = candidate, cand_dist, cand_time
                    improved = True
                    break
            if improved:
                break

    return best


def plan_routes(
    packages: List[Package],
    vehicles: List[Vehicle],
    dist_map: DistanceMap,
) -> Tuple[Dict[str, List[Package]], Dict[str, str]]:
    """
    Assign packages to vehicles with best-insertion and optimise with 2-opt + or-opt.

    Returns:
        assignments  – vehicle_id -> ordered list of assigned packages
        undeliverable – package_id -> reason code for packages that could not be assigned
    """
    # Priority packages first; within the same priority level, earlier time windows first
    sorted_pkgs = sorted(packages, key=lambda p: (-p.priority, p.tw_open, p.tw_close))

    states = [_VehicleState(v) for v in vehicles]
    undeliverable: Dict[str, str] = {}

    for pkg in sorted_pkgs:
        best_cost = float("inf")
        best_state_idx = -1
        best_pos = -1
        blocking: Set[str] = set()

        for s_idx, state in enumerate(states):
            if not state.within_weight(pkg.weight_kg):
                blocking.add("CAPACITY_WEIGHT")
                continue
            if not state.within_volume(pkg.volume_m3):
                blocking.add("CAPACITY_VOLUME")
                continue

            base_dist = state.route_distance
            n = len(state.packages)

            for pos in range(n + 1):
                candidate = state.packages[:pos] + [pkg] + state.packages[pos:]
                result, reason = simulate_route(state.vehicle, candidate, dist_map)
                if result is None:
                    blocking.add(reason)
                    continue
                _, cand_dist, _ = result
                cost = cand_dist - base_dist
                if cost < best_cost - 1e-9:
                    best_cost = cost
                    best_state_idx = s_idx
                    best_pos = pos

        if best_state_idx >= 0:
            state = states[best_state_idx]
            candidate = state.packages[:best_pos] + [pkg] + state.packages[best_pos:]
            result, _ = simulate_route(state.vehicle, candidate, dist_map)
            _, new_dist, _ = result  # type: ignore[misc]
            state.commit_insertion(pkg, best_pos, new_dist)
        else:
            undeliverable[pkg.package_id] = _select_reason(blocking)

    # Improve each vehicle route with local search
    for state in states:
        if len(state.packages) > 1:
            state.packages = _two_opt(state.vehicle, state.packages, dist_map)
            state.packages = _or_opt(state.vehicle, state.packages, dist_map)

    assignments = {state.vehicle.vehicle_id: state.packages for state in states}
    return assignments, undeliverable
