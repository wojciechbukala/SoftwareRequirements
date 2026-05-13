from typing import Dict, List, Optional, Tuple

from .models import DistanceMap, MAX_DRIVER_MINUTES, START_MINUTES, Package, Vehicle
from .route import Route

REASON_CAPACITY_WEIGHT = "CAPACITY_WEIGHT"
REASON_CAPACITY_VOLUME = "CAPACITY_VOLUME"
REASON_UNREACHABLE = "UNREACHABLE"
REASON_TIME_WINDOW = "TIME_WINDOW"
REASON_MAX_DRIVER = "MAX_DRIVER_TIME"
REASON_NO_VEHICLE = "NO_VEHICLE"

# Higher value = package got closer to a successful assignment before failing.
# Used to pick the most informative reason code when all vehicles reject a package.
_REASON_RANK = {
    REASON_NO_VEHICLE: 0,
    REASON_UNREACHABLE: 1,
    REASON_CAPACITY_WEIGHT: 2,
    REASON_CAPACITY_VOLUME: 3,
    REASON_TIME_WINDOW: 4,
    REASON_MAX_DRIVER: 5,
}


def _insertion_delta_distance(
    route: Route, pkg: Package, pos: int, distances: DistanceMap
) -> float:
    """Distance increase caused by inserting pkg at position pos."""
    stops = route.stops
    prev_loc = stops[pos - 1].destination_id if pos > 0 else route.vehicle.depot_location_id
    next_loc = stops[pos].destination_id if pos < len(stops) else route.vehicle.depot_location_id

    old_d = distances.get((prev_loc, next_loc), (float("inf"), 0))[0]
    new_d1 = distances.get((prev_loc, pkg.destination_id), (float("inf"), 0))[0]
    new_d2 = distances.get((pkg.destination_id, next_loc), (float("inf"), 0))[0]
    return new_d1 + new_d2 - old_d


def _insertion_failure_reason(
    route: Route, pkg: Package, pos: int, distances: DistanceMap
) -> Optional[str]:
    """Return the constraint reason that prevents inserting pkg at pos, or None if feasible."""
    new_stops = route.stops[:pos] + [pkg] + route.stops[pos:]
    new_route = Route(route.vehicle, new_stops)

    if not new_route.is_weight_ok():
        return REASON_CAPACITY_WEIGHT
    if not new_route.is_volume_ok():
        return REASON_CAPACITY_VOLUME

    schedule = new_route.compute_schedule(distances)
    if schedule is None:
        # Walk the new stop sequence to distinguish missing edges (UNREACHABLE)
        # from time-window violations (TIME_WINDOW).
        loc = route.vehicle.depot_location_id
        for p in new_stops:
            if (loc, p.destination_id) not in distances:
                return REASON_UNREACHABLE
            loc = p.destination_id
        if (loc, route.vehicle.depot_location_id) not in distances:
            return REASON_UNREACHABLE
        return REASON_TIME_WINDOW

    last_dep = schedule[-1].departure_time
    last_loc = new_stops[-1].destination_id
    _, return_travel = distances.get((last_loc, route.vehicle.depot_location_id), (0, 0))
    duration = last_dep + return_travel - START_MINUTES
    if duration > MAX_DRIVER_MINUTES:
        return REASON_MAX_DRIVER

    return None


def assign_packages(
    packages: List[Package],
    vehicles: List[Vehicle],
    distances: DistanceMap,
) -> Tuple[Dict[str, Route], Dict[str, str]]:
    """Assign packages to vehicles using cheapest-insertion.

    Priority packages (priority=1) are processed before non-priority ones.
    Among packages with the same priority, those with earlier tw_close are
    attempted first so that time-critical deliveries are placed first.

    Returns a dict of routes keyed by vehicle_id and a dict of undeliverable
    packages keyed by package_id with the appropriate reason code.
    """
    routes: Dict[str, Route] = {v.vehicle_id: Route(v) for v in vehicles}
    undeliverable: Dict[str, str] = {}

    sorted_pkgs = sorted(packages, key=lambda p: (-p.priority, p.tw_close))

    for pkg in sorted_pkgs:
        best_vehicle_id: Optional[str] = None
        best_pos: int = 0
        best_delta_dist = float("inf")
        best_delta_dur = float("inf")
        best_reason = REASON_NO_VEHICLE
        best_reason_rank = _REASON_RANK[REASON_NO_VEHICLE]

        for vehicle in vehicles:
            route = routes[vehicle.vehicle_id]

            for pos in range(len(route.stops) + 1):
                reason = _insertion_failure_reason(route, pkg, pos, distances)

                if reason is None:
                    delta_dist = _insertion_delta_distance(route, pkg, pos, distances)
                    new_stops = route.stops[:pos] + [pkg] + route.stops[pos:]
                    new_route = Route(vehicle, new_stops)
                    delta_dur = (
                        new_route.total_duration(distances)
                        - route.total_duration(distances)
                    )

                    if delta_dist < best_delta_dist or (
                        abs(delta_dist - best_delta_dist) < 1e-9
                        and delta_dur < best_delta_dur
                    ):
                        best_vehicle_id = vehicle.vehicle_id
                        best_pos = pos
                        best_delta_dist = delta_dist
                        best_delta_dur = delta_dur
                else:
                    rank = _REASON_RANK.get(reason, 0)
                    if rank > best_reason_rank:
                        best_reason_rank = rank
                        best_reason = reason

        if best_vehicle_id is not None:
            route = routes[best_vehicle_id]
            route.stops = route.stops[:best_pos] + [pkg] + route.stops[best_pos:]
        else:
            undeliverable[pkg.package_id] = best_reason

    return routes, undeliverable
