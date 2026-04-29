from typing import List, Dict, Optional, Tuple
from models import Package, Vehicle, Route, Stop, START_TIME_MIN, MAX_DRIVER_TIME_MIN

# Higher level = package passed more constraint checks before failing = more specific reason.
# When a package fails on multiple vehicles, report the highest-level (most specific) failure.
_FAILURE_LEVEL = {
    "NO_VEHICLE": 0,      # placeholder/fallback
    "CAPACITY_WEIGHT": 1,
    "CAPACITY_VOLUME": 2,
    "UNREACHABLE": 3,
    "TIME_WINDOW": 4,
    "MAX_DRIVER_TIME": 5,
}


def _distance(from_loc: str, to_loc: str, distances: dict) -> Optional[Tuple[float, float]]:
    """Return (distance_km, travel_time_min) or None if unreachable."""
    if from_loc == to_loc:
        return (0.0, 0.0)
    return distances.get((from_loc, to_loc))


def simulate_route(
    vehicle: Vehicle, packages: List[Package], distances: dict
) -> Tuple[Optional[tuple], Optional[str]]:
    """
    Simulate a route for a vehicle visiting packages in the given order.

    Returns ((stops_data, total_distance_km, total_duration_min), None) on success,
    or (None, reason_code) on failure.

    stops_data: list of (package, arrival_time, waiting_time, departure_time)
    """
    if not packages:
        return ([], 0.0, 0), None

    current_time = float(START_TIME_MIN)
    current_loc = vehicle.depot_location_id
    total_distance = 0.0
    stops_data = []

    for pkg in packages:
        leg = _distance(current_loc, pkg.destination_id, distances)
        if leg is None:
            return None, "UNREACHABLE"

        dist_km, travel_min = leg
        arrival = current_time + travel_min

        if arrival > pkg.tw_close:
            return None, "TIME_WINDOW"

        waiting = max(0.0, pkg.tw_open - arrival)
        departure = arrival + waiting + pkg.service_min

        stops_data.append((pkg, arrival, waiting, departure))
        total_distance += dist_km
        current_time = departure
        current_loc = pkg.destination_id

    # Return to depot
    leg = _distance(current_loc, vehicle.depot_location_id, distances)
    if leg is None:
        return None, "UNREACHABLE"

    dist_km, travel_min = leg
    total_distance += dist_km
    total_duration = current_time + travel_min - START_TIME_MIN

    if total_duration > MAX_DRIVER_TIME_MIN:
        return None, "MAX_DRIVER_TIME"

    return (stops_data, total_distance, int(round(total_duration))), None


def _route_distance(vehicle: Vehicle, packages: List[Package], distances: dict) -> float:
    result, _ = simulate_route(vehicle, packages, distances)
    return result[1] if result is not None else float("inf")


def _two_opt(vehicle: Vehicle, packages: List[Package], distances: dict) -> List[Package]:
    """Improve route using 2-opt swaps until no improvement is found."""
    if len(packages) <= 2:
        return packages

    best = packages[:]
    best_dist = _route_distance(vehicle, best, distances)
    improved = True

    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 2, len(best)):
                candidate = best[: i + 1] + best[i + 1 : j + 1][::-1] + best[j + 1 :]
                d = _route_distance(vehicle, candidate, distances)
                if d < best_dist - 1e-9:
                    best = candidate
                    best_dist = d
                    improved = True

    return best


def _find_best_insertion(
    vehicle: Vehicle,
    current_packages: List[Package],
    new_pkg: Package,
    distances: dict,
    current_dist: float,
) -> Tuple[Optional[int], float, str]:
    """
    Try inserting new_pkg at each position in current_packages.
    Returns (best_position, extra_distance, failure_reason).
    best_position is None when no feasible insertion exists.
    """
    total_weight = sum(p.weight_kg for p in current_packages) + new_pkg.weight_kg
    if total_weight > vehicle.max_weight_kg:
        return None, float("inf"), "CAPACITY_WEIGHT"

    total_volume = sum(p.volume_m3 for p in current_packages) + new_pkg.volume_m3
    if total_volume > vehicle.max_volume_m3:
        return None, float("inf"), "CAPACITY_VOLUME"

    best_pos: Optional[int] = None
    best_extra = float("inf")
    failure_reason = "NO_VEHICLE"

    for i in range(len(current_packages) + 1):
        candidate = current_packages[:i] + [new_pkg] + current_packages[i:]
        result, error = simulate_route(vehicle, candidate, distances)
        if result is not None:
            extra = result[1] - current_dist
            if extra < best_extra:
                best_extra = extra
                best_pos = i
        else:
            # Track the "closest to success" failure reason
            if _FAILURE_LEVEL.get(error, 0) > _FAILURE_LEVEL.get(failure_reason, 0):
                failure_reason = error

    return best_pos, best_extra, failure_reason


def _assign_packages(
    vehicles: List[Vehicle], packages: List[Package], distances: dict
) -> Tuple[Dict[str, List[Package]], List[Tuple[Package, str]]]:
    """
    Greedy cheapest-insertion assignment of packages to vehicles.
    Priority packages are processed before non-priority packages.
    Returns (routes_map, undeliverable_list).
    """
    sorted_pkgs = sorted(packages, key=lambda p: (-p.priority, p.tw_open))

    routes: Dict[str, List[Package]] = {v.vehicle_id: [] for v in vehicles}
    route_dists: Dict[str, float] = {v.vehicle_id: 0.0 for v in vehicles}
    undeliverable: List[Tuple[Package, str]] = []

    for pkg in sorted_pkgs:
        best_vehicle: Optional[Vehicle] = None
        best_pos: Optional[int] = None
        best_cost = float("inf")
        best_failure_reason = "NO_VEHICLE"

        for vehicle in vehicles:
            cur_pkgs = routes[vehicle.vehicle_id]
            cur_dist = route_dists[vehicle.vehicle_id]

            pos, extra, reason = _find_best_insertion(
                vehicle, cur_pkgs, pkg, distances, cur_dist
            )

            if pos is not None:
                if extra < best_cost:
                    best_cost = extra
                    best_vehicle = vehicle
                    best_pos = pos
            else:
                if _FAILURE_LEVEL.get(reason, 0) > _FAILURE_LEVEL.get(best_failure_reason, 0):
                    best_failure_reason = reason

        if best_vehicle is not None:
            routes[best_vehicle.vehicle_id].insert(best_pos, pkg)
            result, _ = simulate_route(
                best_vehicle, routes[best_vehicle.vehicle_id], distances
            )
            if result:
                route_dists[best_vehicle.vehicle_id] = result[1]
        else:
            undeliverable.append((pkg, best_failure_reason))

    return routes, undeliverable


def _build_route_objects(
    vehicles: List[Vehicle],
    routes_map: Dict[str, List[Package]],
    distances: dict,
) -> List[Route]:
    route_objects = []
    route_id = 1

    for vehicle in vehicles:
        pkgs = routes_map.get(vehicle.vehicle_id, [])

        if not pkgs:
            route_objects.append(
                Route(route_id=route_id, vehicle=vehicle)
            )
        else:
            optimized = _two_opt(vehicle, pkgs, distances)
            result, _ = simulate_route(vehicle, optimized, distances)

            if result:
                stops_data, total_dist, total_dur = result
                stops = [
                    Stop(
                        package=s[0],
                        arrival_time=int(s[1]),
                        waiting_time=int(s[2]),
                        departure_time=int(s[3]),
                    )
                    for s in stops_data
                ]
                route_objects.append(
                    Route(
                        route_id=route_id,
                        vehicle=vehicle,
                        stops=stops,
                        total_distance_km=total_dist,
                        total_duration_min=total_dur,
                    )
                )
            else:
                # Should not happen; assignment already verified feasibility
                route_objects.append(Route(route_id=route_id, vehicle=vehicle))

        route_id += 1

    return route_objects


def plan(
    vehicles: List[Vehicle], packages: List[Package], distances: dict
) -> Tuple[List[Route], List[Tuple[Package, str]]]:
    """
    Assign packages to vehicles, build and optimise routes.
    Returns (routes, undeliverable_list).
    """
    routes_map, undeliverable = _assign_packages(vehicles, packages, distances)
    routes = _build_route_objects(vehicles, routes_map, distances)
    return routes, undeliverable
