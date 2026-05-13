"""Route assignment and optimization for FleetRouter."""

import sys
from typing import Dict, List, Optional, Tuple

from .models import (
    DEPOT_DEPARTURE_MIN,
    MAX_DRIVER_MIN,
    Package,
    RouteResult,
    StopInfo,
    Vehicle,
)
from .reader import Distances


# Reason reporting precedence when multiple failure reasons exist.
# We report the highest-scoring non-UNREACHABLE reason when any non-UNREACHABLE
# failure exists (package is in principle reachable but blocked by constraints).
# UNREACHABLE is only reported when every vehicle+position attempt fails with it.
_REASON_SCORE = {
    "CAPACITY_WEIGHT": 4,
    "CAPACITY_VOLUME": 3,
    "TIME_WINDOW": 2,
    "MAX_DRIVER_TIME": 1,
    "NO_VEHICLE": 0,
    "UNREACHABLE": -1,  # sentinel – handled separately
}


def compute_route(
    vehicle: Vehicle,
    packages: List[Package],
    distances: Distances,
) -> Tuple[Optional[RouteResult], Optional[str]]:
    """
    Simulate a complete route for a vehicle visiting packages in given order.

    Returns (RouteResult, None) if feasible, or (None, reason_code) if not.
    Reason codes: UNREACHABLE, TIME_WINDOW, MAX_DRIVER_TIME.
    """
    if not packages:
        return RouteResult(stops=[], total_distance=0.0, total_time=0), None

    current_time = DEPOT_DEPARTURE_MIN
    current_loc = vehicle.depot_location_id
    total_dist = 0.0
    stops: List[StopInfo] = []

    for pkg in packages:
        if current_loc == pkg.destination_id:
            dist_km, travel_min = 0.0, 0
        else:
            key = (current_loc, pkg.destination_id)
            if key not in distances:
                return None, "UNREACHABLE"
            dist_km, travel_min = distances[key]

        arrival = current_time + travel_min
        total_dist += dist_km

        service_start = max(arrival, pkg.tw_open)
        if service_start > pkg.tw_close:
            return None, "TIME_WINDOW"

        departure = service_start + pkg.service_min
        stops.append(StopInfo(package=pkg, arrival_time=arrival, departure_time=departure))

        current_time = departure
        current_loc = pkg.destination_id

    # Return to depot
    if current_loc == vehicle.depot_location_id:
        return_dist, return_travel = 0.0, 0
    else:
        key = (current_loc, vehicle.depot_location_id)
        if key not in distances:
            return None, "UNREACHABLE"
        return_dist, return_travel = distances[key]

    total_dist += return_dist
    total_time = current_time + return_travel - DEPOT_DEPARTURE_MIN

    if total_time > MAX_DRIVER_MIN:
        return None, "MAX_DRIVER_TIME"

    return RouteResult(stops=stops, total_distance=total_dist, total_time=total_time), None


def _try_insert(
    vehicle: Vehicle,
    current_packages: List[Package],
    new_pkg: Package,
    pos: int,
    distances: Distances,
    cur_weight: float,
    cur_volume: float,
) -> Tuple[Optional[str], Optional[float]]:
    """
    Attempt inserting new_pkg at position pos in current_packages.

    Returns (None, additional_distance) on success,
    or (reason_code, None) on failure.
    """
    new_weight = cur_weight + new_pkg.weight_kg
    if new_weight > vehicle.max_weight_kg:
        return "CAPACITY_WEIGHT", None

    new_volume = cur_volume + new_pkg.volume_m3
    if new_volume > vehicle.max_volume_m3:
        return "CAPACITY_VOLUME", None

    new_route = current_packages[:pos] + [new_pkg] + current_packages[pos:]
    result, reason = compute_route(vehicle, new_route, distances)

    if result is None:
        return reason, None

    return None, result.total_distance


def two_opt_optimize(
    vehicle: Vehicle,
    packages: List[Package],
    distances: Distances,
) -> List[Package]:
    """
    Apply 2-opt local search to minimize total route distance.
    Respects all constraints (feasible swaps only).
    """
    best = list(packages)
    base_result, _ = compute_route(vehicle, best, distances)
    if base_result is None:
        return best

    best_dist = base_result.total_distance
    improved = True

    while improved:
        improved = False
        n = len(best)
        best_i, best_j = -1, -1

        for i in range(n - 1):
            for j in range(i + 1, n):
                candidate = best[:i] + list(reversed(best[i : j + 1])) + best[j + 1 :]
                result, _ = compute_route(vehicle, candidate, distances)
                if result is not None and result.total_distance < best_dist - 1e-9:
                    best_dist = result.total_distance
                    best_i, best_j = i, j

        if best_i >= 0:
            best = best[:best_i] + list(reversed(best[best_i : best_j + 1])) + best[best_j + 1 :]
            improved = True

    return best


def solve(
    vehicles: List[Vehicle],
    packages: List[Package],
    distances: Distances,
) -> Tuple[Dict[str, List[Package]], List[Tuple[Package, str]]]:
    """
    Assign packages to vehicles using greedy best-insertion, then apply 2-opt.

    Priority packages are processed before non-priority packages.
    Within same priority, packages with tighter (earlier) closing time windows
    are considered first.

    Returns:
        routes: {vehicle_id: ordered list of packages}
        undeliverable: [(Package, reason_code)]
    """
    if not vehicles:
        return {}, [(pkg, "NO_VEHICLE") for pkg in packages]

    # Sort: priority=1 first, then by tw_close ascending (tighter windows first)
    sorted_packages = sorted(packages, key=lambda p: (-p.priority, p.tw_close))

    routes: Dict[str, List[Package]] = {v.vehicle_id: [] for v in vehicles}
    route_weight: Dict[str, float] = {v.vehicle_id: 0.0 for v in vehicles}
    route_volume: Dict[str, float] = {v.vehicle_id: 0.0 for v in vehicles}
    route_dist: Dict[str, float] = {v.vehicle_id: 0.0 for v in vehicles}
    vehicle_map: Dict[str, Vehicle] = {v.vehicle_id: v for v in vehicles}

    undeliverable: List[Tuple[Package, str]] = []

    for pkg in sorted_packages:
        best_cost = float("inf")
        best_vid: Optional[str] = None
        best_pos: int = 0

        # Track failure reasons across all attempts
        seen_non_unreachable: List[str] = []
        all_unreachable = True  # True until we see a non-UNREACHABLE failure

        for vehicle in vehicles:
            vid = vehicle.vehicle_id
            current = routes[vid]
            cur_w = route_weight[vid]
            cur_v = route_volume[vid]
            cur_d = route_dist[vid]

            for pos in range(len(current) + 1):
                reason, new_dist = _try_insert(
                    vehicle, current, pkg, pos, distances, cur_w, cur_v
                )

                if reason is not None:
                    if reason != "UNREACHABLE":
                        all_unreachable = False
                        seen_non_unreachable.append(reason)
                    continue

                # Feasible insertion found; compute marginal cost
                cost = (new_dist or 0.0) - cur_d
                all_unreachable = False  # At least one feasible position exists

                if cost < best_cost:
                    best_cost = cost
                    best_vid = vid
                    best_pos = pos

        if best_vid is None:
            # Determine failure reason
            if all_unreachable and not seen_non_unreachable:
                reason_code = "UNREACHABLE"
            elif seen_non_unreachable:
                # Pick highest-scoring non-UNREACHABLE reason
                reason_code = max(
                    seen_non_unreachable, key=lambda r: _REASON_SCORE.get(r, 0)
                )
            else:
                reason_code = "NO_VEHICLE"

            undeliverable.append((pkg, reason_code))
        else:
            # Insert package into the best vehicle at the best position
            vehicle = vehicle_map[best_vid]
            current = routes[best_vid]
            new_route = current[:best_pos] + [pkg] + current[best_pos:]
            routes[best_vid] = new_route
            route_weight[best_vid] += pkg.weight_kg
            route_volume[best_vid] += pkg.volume_m3

            result, _ = compute_route(vehicle, new_route, distances)
            route_dist[best_vid] = result.total_distance if result else 0.0

    # Apply 2-opt optimization to each non-empty route
    for vid, pkgs in routes.items():
        if len(pkgs) > 1:
            vehicle = vehicle_map[vid]
            routes[vid] = two_opt_optimize(vehicle, pkgs, distances)

    return routes, undeliverable
