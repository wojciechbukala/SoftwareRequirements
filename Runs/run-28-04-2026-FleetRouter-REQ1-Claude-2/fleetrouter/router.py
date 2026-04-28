"""Core routing engine for FleetRouter."""
from typing import Dict, List, Optional, Tuple

from .models import (
    Package, Vehicle, Route, Stop,
    DEPOT_DEPARTURE, MAX_DRIVER_MINUTES
)

Distances = Dict[Tuple[str, str], Tuple[float, int]]
Packages = Dict[str, Package]


def _get_dist(distances: Distances, from_id: str, to_id: str) -> Optional[Tuple[float, int]]:
    if from_id == to_id:
        return (0.0, 0)
    return distances.get((from_id, to_id))


def _simulate(vehicle: Vehicle, package_ids: List[str],
              packages: Packages,
              distances: Distances) -> Optional[Tuple[List[Stop], float, int]]:
    """
    Simulate a full route and return (stops_with_depot_ends, distance_km, duration_min)
    or None if infeasible for any reason.
    """
    stops: List[Stop] = []
    current_loc = vehicle.depot_id
    current_time = DEPOT_DEPARTURE
    total_distance = 0.0

    stops.append(Stop(vehicle.depot_id, None, DEPOT_DEPARTURE, DEPOT_DEPARTURE))

    for pkg_id in package_ids:
        pkg = packages[pkg_id]
        edge = _get_dist(distances, current_loc, pkg.location_id)
        if edge is None:
            return None
        dist_km, travel_min = edge

        arrival = current_time + travel_min
        if arrival > pkg.time_close:
            return None

        service_start = max(arrival, pkg.time_open)
        departure = service_start + pkg.service_duration

        stops.append(Stop(pkg.location_id, pkg_id, arrival, departure))
        total_distance += dist_km
        current_time = departure
        current_loc = pkg.location_id

    edge = _get_dist(distances, current_loc, vehicle.depot_id)
    if edge is None:
        return None
    dist_km, travel_min = edge
    depot_return_time = current_time + travel_min
    total_distance += dist_km
    total_duration = depot_return_time - DEPOT_DEPARTURE

    if total_duration > MAX_DRIVER_MINUTES:
        return None

    stops.append(Stop(vehicle.depot_id, None, depot_return_time, depot_return_time))
    return stops, total_distance, total_duration


def _find_best_insertion(vehicle: Vehicle, route: Route,
                         pkg: Package,
                         packages: Packages,
                         distances: Distances) -> Optional[Tuple[int, float, int]]:
    """
    Find cheapest valid insertion position for pkg.
    Returns (position, added_dist, added_dur) or None.
    """
    if route.weight_used + pkg.weight > vehicle.max_weight:
        return None
    if route.volume_used + pkg.volume > vehicle.max_volume:
        return None

    best_pos = None
    best_add_dist = float('inf')
    best_add_dur = float('inf')
    n = len(route.package_ids)

    for pos in range(n + 1):
        new_order = route.package_ids[:pos] + [pkg.id] + route.package_ids[pos:]
        result = _simulate(vehicle, new_order, packages, distances)
        if result is None:
            continue
        _, new_dist, new_dur = result
        add_dist = new_dist - route.total_distance
        add_dur = new_dur - route.total_duration
        if (add_dist < best_add_dist or
                (add_dist == best_add_dist and add_dur < best_add_dur)):
            best_add_dist = add_dist
            best_add_dur = add_dur
            best_pos = pos

    return (best_pos, best_add_dist, best_add_dur) if best_pos is not None else None


def _two_opt(vehicle: Vehicle, package_ids: List[str],
             packages: Packages,
             distances: Distances) -> Tuple[List[str], float, int]:
    """Apply 2-opt improvement until no improvement found."""
    best_ids = list(package_ids)
    result = _simulate(vehicle, best_ids, packages, distances)
    if result is None:
        return best_ids, 0.0, 0
    _, best_dist, best_dur = result
    improved = True

    while improved:
        improved = False
        n = len(best_ids)
        for i in range(n - 1):
            for j in range(i + 1, n):
                new_ids = best_ids[:i] + list(reversed(best_ids[i:j + 1])) + best_ids[j + 1:]
                res = _simulate(vehicle, new_ids, packages, distances)
                if res is None:
                    continue
                _, nd, ndu = res
                if nd < best_dist or (nd == best_dist and ndu < best_dur):
                    best_ids = new_ids
                    best_dist = nd
                    best_dur = ndu
                    improved = True
                    break
            if improved:
                break

    return best_ids, best_dist, best_dur


def _determine_reason(pkg: Package, routes: List[Route],
                      vehicles: List[Vehicle],
                      packages: Packages,
                      distances: Distances) -> str:
    """
    Determine the single reason code for why a package cannot be delivered.
    Precedence: CAPACITY_WEIGHT > CAPACITY_VOLUME > TIME_WINDOW >
                MAX_DRIVER_TIME > UNREACHABLE > NO_VEHICLE
    """
    pairs = list(zip(vehicles, routes))

    # 1. CAPACITY_WEIGHT: no vehicle has enough remaining weight
    if all(r.weight_used + pkg.weight > v.max_weight for v, r in pairs):
        return 'CAPACITY_WEIGHT'

    # 2. CAPACITY_VOLUME: no vehicle has enough remaining volume
    if all(r.volume_used + pkg.volume > v.max_volume for v, r in pairs):
        return 'CAPACITY_VOLUME'

    # 3. TIME_WINDOW: for all vehicles with sufficient capacity,
    #    the earliest possible arrival (direct from depot) exceeds close time.
    cap_ok_pairs = [(v, r) for v, r in pairs
                    if r.weight_used + pkg.weight <= v.max_weight
                    and r.volume_used + pkg.volume <= v.max_volume]

    if cap_ok_pairs:
        def time_feasible_direct(v: Vehicle) -> bool:
            edge = _get_dist(distances, v.depot_id, pkg.location_id)
            if edge is None:
                return False
            _, travel = edge
            return DEPOT_DEPARTURE + travel <= pkg.time_close

        if not any(time_feasible_direct(v) for v, _ in cap_ok_pairs):
            return 'TIME_WINDOW'

    # 4. MAX_DRIVER_TIME: for every vehicle (with capacity), adding the package
    #    would exceed 8 hours even at the best position
    def driver_time_ok(v: Vehicle, r: Route) -> bool:
        if r.weight_used + pkg.weight > v.max_weight:
            return True  # not a driver time issue
        if r.volume_used + pkg.volume > v.max_volume:
            return True
        # Try all positions
        n = len(r.package_ids)
        for pos in range(n + 1):
            new_order = r.package_ids[:pos] + [pkg.id] + r.package_ids[pos:]
            res = _simulate(v, new_order, packages, distances)
            if res is not None:
                return True
        return False

    cap_ok = any(r.weight_used + pkg.weight <= v.max_weight and
                 r.volume_used + pkg.volume <= v.max_volume
                 for v, r in pairs)
    if cap_ok and not any(driver_time_ok(v, r) for v, r in pairs):
        return 'MAX_DRIVER_TIME'

    # 5. UNREACHABLE: no vehicle can reach pkg from depot and back
    if not any(_get_dist(distances, v.depot_id, pkg.location_id) is not None and
               _get_dist(distances, pkg.location_id, v.depot_id) is not None
               for v, _ in pairs):
        return 'UNREACHABLE'

    return 'NO_VEHICLE'


def plan_routes(vehicles: List[Vehicle],
                packages_list: List[Package],
                distances: Distances) -> Tuple[List[Route], List[Tuple[str, str]]]:
    """
    Main planning function.
    Returns (routes, undeliverable_list).
    """
    packages = {p.id: p for p in packages_list}

    routes: List[Route] = []
    for v in vehicles:
        routes.append(Route(vehicle=v))

    undeliverable: List[Tuple[str, str]] = []

    # Priority first, then urgency (earliest close, then earliest open)
    sorted_pkgs = sorted(
        packages_list,
        key=lambda p: (0 if p.priority else 1, p.time_close, p.time_open)
    )

    for pkg in sorted_pkgs:
        best_v_idx = None
        best_pos = None
        best_add_dist = float('inf')
        best_add_dur = float('inf')

        for idx, (v, r) in enumerate(zip(vehicles, routes)):
            result = _find_best_insertion(v, r, pkg, packages, distances)
            if result is None:
                continue
            pos, add_dist, add_dur = result
            if (add_dist < best_add_dist or
                    (add_dist == best_add_dist and add_dur < best_add_dur)):
                best_add_dist = add_dist
                best_add_dur = add_dur
                best_pos = pos
                best_v_idx = idx

        if best_v_idx is None:
            reason = _determine_reason(pkg, routes, vehicles, packages, distances)
            undeliverable.append((pkg.id, reason))
        else:
            r = routes[best_v_idx]
            v = vehicles[best_v_idx]
            r.package_ids.insert(best_pos, pkg.id)
            r.weight_used += pkg.weight
            r.volume_used += pkg.volume
            sim = _simulate(v, r.package_ids, packages, distances)
            if sim:
                r.stops, r.total_distance, r.total_duration = sim

    # 2-opt optimization
    for v, r in zip(vehicles, routes):
        if len(r.package_ids) < 2:
            if len(r.package_ids) == 1:
                sim = _simulate(v, r.package_ids, packages, distances)
                if sim:
                    r.stops, r.total_distance, r.total_duration = sim
            continue
        new_ids, new_dist, new_dur = _two_opt(v, r.package_ids, packages, distances)
        if (new_dist < r.total_distance or
                (new_dist == r.total_distance and new_dur < r.total_duration)):
            r.package_ids = new_ids
            r.total_distance = new_dist
            r.total_duration = new_dur
        sim = _simulate(v, r.package_ids, packages, distances)
        if sim:
            r.stops, r.total_distance, r.total_duration = sim

    return routes, undeliverable
