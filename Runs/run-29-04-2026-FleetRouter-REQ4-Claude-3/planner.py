"""
VRP with Time Windows solver.

Strategy:
  1. Identify inherently undeliverable packages via the Alloy predicates.
  2. Two-pass greedy cheapest-insertion:
       Pass 1 – priority packages (priority == 1), sorted by tw_close ascending.
       Pass 2 – non-priority packages, sorted by tw_close ascending.
     Priority packages are always assigned before non-priority ones, which
     satisfies the requirement that capacity conflicts drop non-priority packages.
  3. Intra-route 2-opt improvement to minimise total distance (tiebreak: total time).
"""
from typing import Dict, List, Optional, Tuple

from models import InputData, Package, PlanResult, Route, RouteStop, Vehicle
from validator import (
    REASON_NO_VEHICLE,
    distance_km,
    find_inherently_undeliverable,
    travel_time,
)

_INF = float("inf")


# ---------------------------------------------------------------------------
# Route time and distance helpers
# ---------------------------------------------------------------------------

def _compute_times(
    vehicle: Vehicle,
    sequence: List[str],
    packages: Dict[str, Package],
    distances: Dict,
) -> Optional[Tuple[List[Tuple[str, str, int, int]], int]]:
    """
    Simulate driving the given package sequence for vehicle.

    Returns (stops, depot_arrival_min) where stops is a list of
    (pkg_id, location_id, arrival_min, departure_min), or None if infeasible.
    """
    depot = vehicle.depot_location_id
    current_time = 0
    current_loc = depot
    stops = []

    for pkg_id in sequence:
        pkg = packages[pkg_id]
        t = travel_time(current_loc, pkg.destination_id, distances)
        if t is None:
            return None
        arrival = current_time + t
        if arrival > pkg.tw_close:
            return None
        departure = max(arrival, pkg.tw_open) + pkg.service_min
        stops.append((pkg_id, pkg.destination_id, arrival, departure))
        current_time = departure
        current_loc = pkg.destination_id

    t = travel_time(current_loc, depot, distances)
    if t is None:
        return None
    depot_arrival = current_time + t
    if depot_arrival > 480:
        return None

    return stops, depot_arrival


def _route_distance(
    vehicle: Vehicle,
    sequence: List[str],
    packages: Dict[str, Package],
    distances: Dict,
) -> float:
    depot = vehicle.depot_location_id
    total = 0.0
    current_loc = depot
    for pkg_id in sequence:
        loc = packages[pkg_id].destination_id
        d = distance_km(current_loc, loc, distances)
        if d is None:
            return _INF
        total += d
        current_loc = loc
    d = distance_km(current_loc, depot, distances)
    if d is None:
        return _INF
    total += d
    return total


# ---------------------------------------------------------------------------
# Route state (mutable during construction)
# ---------------------------------------------------------------------------

class _RouteState:
    def __init__(self, vehicle: Vehicle) -> None:
        self.vehicle = vehicle
        self.sequence: List[str] = []
        self.total_weight = 0.0
        self.total_volume = 0.0

    def find_best_insertion(
        self,
        pkg: Package,
        packages: Dict[str, Package],
        distances: Dict,
    ) -> Optional[Tuple[int, float]]:
        """
        Return (position, extra_distance_km) for the cheapest feasible insertion,
        or None if the package cannot be added to this route.
        """
        if self.total_weight + pkg.weight_kg > self.vehicle.max_weight_kg:
            return None
        if self.total_volume + pkg.volume_m3 > self.vehicle.max_volume_m3:
            return None

        depot = self.vehicle.depot_location_id
        seq = self.sequence
        n = len(seq)
        best_pos: Optional[int] = None
        best_extra = _INF

        for pos in range(n + 1):
            prev_loc = depot if pos == 0 else packages[seq[pos - 1]].destination_id
            next_loc = depot if pos == n else packages[seq[pos]].destination_id
            pkg_loc = pkg.destination_id

            old_d = distance_km(prev_loc, next_loc, distances)
            d_in = distance_km(prev_loc, pkg_loc, distances)
            d_out = distance_km(pkg_loc, next_loc, distances)
            if old_d is None or d_in is None or d_out is None:
                continue

            extra = d_in + d_out - old_d

            new_seq = seq[:pos] + [pkg.package_id] + seq[pos:]
            if _compute_times(self.vehicle, new_seq, packages, distances) is None:
                continue

            if extra < best_extra:
                best_extra = extra
                best_pos = pos

        return (best_pos, best_extra) if best_pos is not None else None

    def insert(self, pkg: Package, position: int) -> None:
        self.sequence.insert(position, pkg.package_id)
        self.total_weight += pkg.weight_kg
        self.total_volume += pkg.volume_m3

    def to_route(
        self, packages: Dict[str, Package], distances: Dict
    ) -> Optional[Route]:
        if not self.sequence:
            return None
        result = _compute_times(self.vehicle, self.sequence, packages, distances)
        if result is None:
            return None
        stops_data, depot_arrival = result
        total_dist = _route_distance(self.vehicle, self.sequence, packages, distances)
        stops = [
            RouteStop(
                position=i + 1,
                package_id=pkg_id,
                location_id=loc_id,
                arrival_min=arrival,
                departure_min=departure,
            )
            for i, (pkg_id, loc_id, arrival, departure) in enumerate(stops_data)
        ]
        return Route(
            route_id=self.vehicle.vehicle_id,
            vehicle=self.vehicle,
            stops=stops,
            depot_arrival_min=depot_arrival,
            total_distance_km=total_dist,
        )


# ---------------------------------------------------------------------------
# 2-opt intra-route improvement
# ---------------------------------------------------------------------------

def _two_opt(
    state: _RouteState, packages: Dict[str, Package], distances: Dict
) -> None:
    """Improve route distance in-place using 2-opt until no improvement is found."""
    improved = True
    while improved:
        improved = False
        seq = state.sequence
        n = len(seq)
        if n < 2:
            break
        current_dist = _route_distance(state.vehicle, seq, packages, distances)

        for i in range(n - 1):
            for j in range(i + 1, n):
                new_seq = seq[:i] + seq[i : j + 1][::-1] + seq[j + 1 :]
                result = _compute_times(state.vehicle, new_seq, packages, distances)
                if result is None:
                    continue
                new_dist = _route_distance(state.vehicle, new_seq, packages, distances)
                if new_dist < current_dist - 1e-9:
                    state.sequence = new_seq
                    current_dist = new_dist
                    improved = True
                    break
            if improved:
                break


# ---------------------------------------------------------------------------
# Main planner
# ---------------------------------------------------------------------------

def _assign_packages(
    packages_to_assign: List[Package],
    route_states: Dict[str, _RouteState],
    packages: Dict[str, Package],
    distances: Dict,
) -> List[str]:
    """Greedy cheapest-insertion for a list of packages. Returns unassigned package IDs."""
    unassigned = []
    for pkg in packages_to_assign:
        best_vehicle: Optional[str] = None
        best_pos: Optional[int] = None
        best_extra = _INF
        best_current_dist = _INF

        for v_id, rs in route_states.items():
            result = rs.find_best_insertion(pkg, packages, distances)
            if result is None:
                continue
            pos, extra = result
            current_dist = _route_distance(rs.vehicle, rs.sequence, packages, distances)
            # Primary: minimise extra distance; tiebreak: prefer shorter current route
            if extra < best_extra or (
                abs(extra - best_extra) < 1e-9 and current_dist < best_current_dist
            ):
                best_extra = extra
                best_vehicle = v_id
                best_pos = pos
                best_current_dist = current_dist

        if best_vehicle is not None:
            route_states[best_vehicle].insert(pkg, best_pos)
        else:
            unassigned.append(pkg.package_id)
    return unassigned


def solve(data: InputData) -> PlanResult:
    packages = data.packages
    vehicles = data.vehicles
    distances = data.distances

    # Step 1 – inherently undeliverable packages
    undeliverable: Dict[str, str] = find_inherently_undeliverable(
        packages, vehicles, distances
    )

    # Step 2 – deliverable candidates
    deliverable = {
        pid: pkg for pid, pkg in packages.items() if pid not in undeliverable
    }

    # Step 3 – separate by priority, sort by tw_close (tightest first)
    priority_pkgs = sorted(
        (p for p in deliverable.values() if p.priority == 1),
        key=lambda p: p.tw_close,
    )
    normal_pkgs = sorted(
        (p for p in deliverable.values() if p.priority == 0),
        key=lambda p: p.tw_close,
    )

    # Step 4 – initialise one route state per vehicle
    route_states: Dict[str, _RouteState] = {
        v_id: _RouteState(v) for v_id, v in vehicles.items()
    }

    # Step 5 – assign priority packages first, then non-priority
    unassigned_ids = _assign_packages(priority_pkgs, route_states, packages, distances)
    unassigned_ids += _assign_packages(normal_pkgs, route_states, packages, distances)

    for pkg_id in unassigned_ids:
        undeliverable[pkg_id] = REASON_NO_VEHICLE

    # Step 6 – 2-opt improvement
    for rs in route_states.values():
        _two_opt(rs, packages, distances)

    # Step 7 – build final Route objects
    routes: List[Route] = []
    for rs in route_states.values():
        route = rs.to_route(packages, distances)
        if route is not None:
            routes.append(route)

    # Sort routes for deterministic output
    routes.sort(key=lambda r: r.vehicle.vehicle_id)

    return PlanResult(routes=routes, undeliverable=undeliverable)
