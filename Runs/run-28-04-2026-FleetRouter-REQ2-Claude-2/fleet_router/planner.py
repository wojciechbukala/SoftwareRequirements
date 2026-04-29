from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .models import (
    DEPOT_DEPARTURE_TIME,
    MAX_DRIVER_TIME_MIN,
    DistanceEntry,
    Package,
    Route,
    Stop,
    Vehicle,
)

Distances = Dict[Tuple[str, str], DistanceEntry]
StopData = Tuple[str, Package]  # (location_id, package)


def simulate_route(
    depot_id: str,
    stops: List[StopData],
    distances: Distances,
) -> Tuple[Optional[float], Optional[int], Optional[List[Tuple[int, int]]], Optional[str]]:
    """Simulate route execution from depot through stops and back.

    Returns (total_distance_km, total_time_min, [(arrival, departure)...], failure_reason).
    failure_reason is None on success.
    """
    if not stops:
        return 0.0, 0, [], None

    current_location = depot_id
    current_time = DEPOT_DEPARTURE_TIME
    total_distance = 0.0
    stop_times: List[Tuple[int, int]] = []

    for location_id, package in stops:
        key = (current_location, location_id)
        if key not in distances:
            return None, None, None, "UNREACHABLE"

        entry = distances[key]
        arrival = current_time + entry.travel_time_min

        if arrival > package.tw_close:
            return None, None, None, "TIME_WINDOW"

        departure = max(arrival, package.tw_open) + package.service_min

        total_distance += entry.distance_km
        stop_times.append((arrival, departure))
        current_time = departure
        current_location = location_id

    key = (current_location, depot_id)
    if key not in distances:
        return None, None, None, "UNREACHABLE"

    entry = distances[key]
    total_distance += entry.distance_km
    total_time = current_time + entry.travel_time_min - DEPOT_DEPARTURE_TIME

    if total_time > MAX_DRIVER_TIME_MIN:
        return None, None, None, "MAX_DRIVER_TIME"

    return total_distance, total_time, stop_times, None


def _best_routing_failure(reasons: List[str]) -> str:
    """Determine the most informative routing failure reason from a list."""
    if not reasons:
        return "NO_VEHICLE"
    if all(r == "UNREACHABLE" for r in reasons):
        return "UNREACHABLE"
    for priority_reason in ("TIME_WINDOW", "MAX_DRIVER_TIME"):
        if priority_reason in reasons:
            return priority_reason
    if "UNREACHABLE" in reasons:
        return "UNREACHABLE"
    return "NO_VEHICLE"


def find_best_insertion(
    depot_id: str,
    assigned_stops: List[StopData],
    package: Package,
    distances: Distances,
) -> Tuple[Optional[int], Optional[float], Optional[str]]:
    """Find the best insertion position for a package in the current route.

    Returns (insertion_index, resulting_total_distance, failure_reason).
    failure_reason is None on success.
    """
    best_pos: Optional[int] = None
    best_dist = float("inf")
    failure_reasons: List[str] = []

    for pos in range(len(assigned_stops) + 1):
        candidate = (
            assigned_stops[:pos]
            + [(package.destination_id, package)]
            + assigned_stops[pos:]
        )
        dist, _, _, reason = simulate_route(depot_id, candidate, distances)
        if reason is None and dist is not None:
            if dist < best_dist:
                best_dist = dist
                best_pos = pos
        elif reason:
            failure_reasons.append(reason)

    if best_pos is not None:
        return best_pos, best_dist, None

    return None, None, _best_routing_failure(failure_reasons)


@dataclass
class VehicleState:
    vehicle: Vehicle
    assigned_stops: List[StopData] = field(default_factory=list)
    current_weight: float = 0.0
    current_volume: float = 0.0
    current_route_distance: float = 0.0


def assign_packages(
    packages: List[Package],
    vehicles: List[Vehicle],
    distances: Distances,
) -> Tuple[Dict[str, VehicleState], List[Tuple[str, str]]]:
    """Assign packages to vehicles using a greedy best-insertion heuristic.

    Packages are processed priority-first, then by earliest time-window close.
    Returns (vehicle_states, [(package_id, reason), ...]) for undeliverable packages.
    """
    sorted_packages = sorted(packages, key=lambda p: (-p.priority, p.tw_close))
    states = {v.id: VehicleState(vehicle=v) for v in vehicles}
    undeliverable: List[Tuple[str, str]] = []

    for package in sorted_packages:
        best_vehicle_id: Optional[str] = None
        best_pos: Optional[int] = None
        best_added_dist = float("inf")

        capacity_weight_fails = 0
        capacity_volume_fails = 0
        routing_failure_reasons: List[str] = []

        for v_id, state in states.items():
            if state.current_weight + package.weight_kg > state.vehicle.max_weight_kg:
                capacity_weight_fails += 1
                continue
            if state.current_volume + package.volume_m3 > state.vehicle.max_volume_m3:
                capacity_volume_fails += 1
                continue

            pos, new_dist, routing_reason = find_best_insertion(
                state.vehicle.depot_location_id,
                state.assigned_stops,
                package,
                distances,
            )
            if pos is not None and new_dist is not None:
                added = new_dist - state.current_route_distance
                if added < best_added_dist:
                    best_added_dist = added
                    best_vehicle_id = v_id
                    best_pos = pos
            else:
                routing_failure_reasons.append(routing_reason or "NO_VEHICLE")

        if best_vehicle_id is not None and best_pos is not None:
            state = states[best_vehicle_id]
            state.assigned_stops.insert(best_pos, (package.destination_id, package))
            state.current_weight += package.weight_kg
            state.current_volume += package.volume_m3
            # Recompute route distance after insertion
            dist, _, _, _ = simulate_route(
                state.vehicle.depot_location_id, state.assigned_stops, distances
            )
            state.current_route_distance = dist or 0.0
        else:
            overall_reason = _determine_undeliverable_reason(
                capacity_weight_fails,
                capacity_volume_fails,
                routing_failure_reasons,
            )
            undeliverable.append((package.id, overall_reason))

    return states, undeliverable


def _determine_undeliverable_reason(
    capacity_weight_fails: int,
    capacity_volume_fails: int,
    routing_failure_reasons: List[str],
) -> str:
    """Determine the most informative reason a package could not be assigned."""
    if not routing_failure_reasons:
        # All vehicles failed at capacity check
        if capacity_weight_fails >= capacity_volume_fails and capacity_weight_fails > 0:
            return "CAPACITY_WEIGHT"
        if capacity_volume_fails > 0:
            return "CAPACITY_VOLUME"
        return "NO_VEHICLE"

    # At least one vehicle had capacity — use routing failure
    return _best_routing_failure(routing_failure_reasons)


def _two_opt_pass(
    depot_id: str,
    stops: List[StopData],
    distances: Distances,
    best_dist: float,
    best_time: int,
) -> Tuple[Optional[List[StopData]], float, int]:
    """Perform one full 2-opt pass. Return (improved_stops, dist, time) or (None, ...) if no improvement."""
    n = len(stops)
    for i in range(n - 1):
        for j in range(i + 1, n):
            candidate = stops[:i] + stops[i : j + 1][::-1] + stops[j + 1 :]
            dist, time, _, reason = simulate_route(depot_id, candidate, distances)
            if reason is None and dist is not None and time is not None:
                if dist < best_dist - 1e-9 or (
                    abs(dist - best_dist) < 1e-9 and time < best_time
                ):
                    return candidate, dist, time
    return None, best_dist, best_time


def _or_opt_pass(
    depot_id: str,
    stops: List[StopData],
    distances: Distances,
    best_dist: float,
    best_time: int,
) -> Tuple[Optional[List[StopData]], float, int]:
    """Perform one full or-opt pass (single-stop relocation).

    Return (improved_stops, dist, time) or (None, ...) if no improvement.
    """
    n = len(stops)
    for i in range(n):
        stop = stops[i]
        remaining = stops[:i] + stops[i + 1 :]
        for j in range(len(remaining) + 1):
            if j == i:
                continue
            candidate = remaining[:j] + [stop] + remaining[j:]
            dist, time, _, reason = simulate_route(depot_id, candidate, distances)
            if reason is None and dist is not None and time is not None:
                if dist < best_dist - 1e-9 or (
                    abs(dist - best_dist) < 1e-9 and time < best_time
                ):
                    return candidate, dist, time
    return None, best_dist, best_time


def optimize_route(
    depot_id: str,
    stops: List[StopData],
    distances: Distances,
) -> Tuple[List[StopData], float, int]:
    """Improve route ordering with 2-opt and or-opt local search."""
    if len(stops) <= 1:
        dist, time, _, _ = simulate_route(depot_id, stops, distances)
        return stops, dist or 0.0, time or 0

    best_stops = stops[:]
    dist_result, time_result, _, _ = simulate_route(depot_id, best_stops, distances)
    best_dist = dist_result or 0.0
    best_time = time_result or 0

    improved = True
    while improved:
        improved = False

        candidate, new_dist, new_time = _two_opt_pass(
            depot_id, best_stops, distances, best_dist, best_time
        )
        if candidate is not None:
            best_stops, best_dist, best_time = candidate, new_dist, new_time
            improved = True
            continue

        candidate, new_dist, new_time = _or_opt_pass(
            depot_id, best_stops, distances, best_dist, best_time
        )
        if candidate is not None:
            best_stops, best_dist, best_time = candidate, new_dist, new_time
            improved = True

    return best_stops, best_dist, best_time


def build_routes(
    states: Dict[str, VehicleState],
    all_vehicles: List[Vehicle],
    distances: Distances,
) -> List[Route]:
    """Build optimized Route objects for all vehicles."""
    routes: List[Route] = []

    for vehicle in all_vehicles:
        state = states[vehicle.id]

        if not state.assigned_stops:
            routes.append(
                Route(
                    vehicle_id=vehicle.id,
                    depot_id=vehicle.depot_location_id,
                    stops=[],
                    total_distance_km=0.0,
                    total_time_min=0,
                )
            )
            continue

        optimized_stops, total_dist, total_time = optimize_route(
            vehicle.depot_location_id, state.assigned_stops, distances
        )

        _, _, stop_times, _ = simulate_route(
            vehicle.depot_location_id, optimized_stops, distances
        )

        stops: List[Stop] = []
        for position, ((location_id, package), (arrival, departure)) in enumerate(
            zip(optimized_stops, stop_times or []), start=1
        ):
            stops.append(
                Stop(
                    position=position,
                    location_id=location_id,
                    package_id=package.id,
                    arrival_time=arrival,
                    departure_time=departure,
                )
            )

        routes.append(
            Route(
                vehicle_id=vehicle.id,
                depot_id=vehicle.depot_location_id,
                stops=stops,
                total_distance_km=total_dist,
                total_time_min=total_time,
            )
        )

    return routes
