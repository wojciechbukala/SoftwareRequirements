"""
VRP solver for FleetRouter.

Algorithm:
  1. Sort feasible packages: priority desc, then tw_close asc (earliest deadline first).
  2. Cheapest-insertion construction: for each package, find the route+position that
     minimises added distance while satisfying all constraints. If no route fits, open
     a new route on the next available vehicle. If no vehicle is left, mark undeliverable.
  3. 2-opt improvement within each route.
  4. Or-opt inter-route improvement (move single packages between routes).
"""
from typing import Dict, List, Optional, Tuple

from models import Package, Vehicle, Route, DeliveryStop, DepotStop
from feasibility import get_travel_time, get_distance_km, MAX_DRIVER_MINUTES


def _route_distance(sequence: List[Package], depot_id: str, distances: Dict) -> float:
    if not sequence:
        km = (get_distance_km(distances, depot_id, depot_id) or 0.0)
        return km
    total = 0.0
    prev = depot_id
    for pkg in sequence:
        d = get_distance_km(distances, prev, pkg.destination_id)
        total += (d or 0.0)
        prev = pkg.destination_id
    d = get_distance_km(distances, prev, depot_id)
    total += (d or 0.0)
    return total


def _compute_times(sequence: List[Package], depot_id: str,
                   distances: Dict) -> Optional[Tuple[List[Tuple[int, int]], int]]:
    """
    Compute (arrival, departure) for each delivery stop and end_arrival (return to depot).
    Returns None if any constraint is violated (unreachable segment, time window exceeded,
    or driver time exceeded).
    """
    times: List[Tuple[int, int]] = []
    current_time = 0
    current_loc = depot_id

    for pkg in sequence:
        travel = get_travel_time(distances, current_loc, pkg.destination_id)
        if travel is None:
            return None
        arrival = current_time + travel
        if arrival > pkg.tw_close:
            return None
        departure = max(arrival, pkg.tw_open) + pkg.service_min
        times.append((arrival, departure))
        current_time = departure
        current_loc = pkg.destination_id

    travel = get_travel_time(distances, current_loc, depot_id)
    if travel is None:
        return None
    end_arrival = current_time + travel
    if end_arrival > MAX_DRIVER_MINUTES:
        return None

    return times, end_arrival


def _capacity_ok(sequence: List[Package], vehicle: Vehicle) -> bool:
    total_w = sum(p.weight_kg for p in sequence)
    total_v = sum(p.volume_m3 for p in sequence)
    return total_w <= vehicle.max_weight_kg and total_v <= vehicle.max_volume_m3


class _RouteState:
    def __init__(self, vehicle: Vehicle, route_id: str):
        self.vehicle = vehicle
        self.route_id = route_id
        self.sequence: List[Package] = []
        self.times: List[Tuple[int, int]] = []  # (arrival, departure) per stop
        self.end_arrival: int = 0
        self.distance: float = 0.0

    @property
    def depot_id(self) -> str:
        return self.vehicle.depot_location_id

    def try_insert(self, pkg: Package, distances: Dict) -> Optional[Tuple[int, float]]:
        """
        Find best insertion position for pkg. Returns (position, marginal_cost) or None.
        """
        best_pos: Optional[int] = None
        best_delta = float("inf")

        n = len(self.sequence)
        for pos in range(n + 1):
            new_seq = self.sequence[:pos] + [pkg] + self.sequence[pos:]
            if not _capacity_ok(new_seq, self.vehicle):
                continue
            result = _compute_times(new_seq, self.depot_id, distances)
            if result is None:
                continue
            new_dist = _route_distance(new_seq, self.depot_id, distances)
            delta = new_dist - self.distance
            if delta < best_delta:
                best_delta = delta
                best_pos = pos

        if best_pos is None:
            return None
        return best_pos, best_delta

    def insert(self, pkg: Package, pos: int, distances: Dict) -> None:
        self.sequence = self.sequence[:pos] + [pkg] + self.sequence[pos:]
        result = _compute_times(self.sequence, self.depot_id, distances)
        assert result is not None
        self.times, self.end_arrival = result
        self.distance = _route_distance(self.sequence, self.depot_id, distances)

    def remove(self, pos: int, distances: Dict) -> Package:
        pkg = self.sequence[pos]
        self.sequence = self.sequence[:pos] + self.sequence[pos + 1:]
        if self.sequence:
            result = _compute_times(self.sequence, self.depot_id, distances)
            assert result is not None
            self.times, self.end_arrival = result
        else:
            self.times = []
            travel = get_travel_time(distances, self.depot_id, self.depot_id)
            self.end_arrival = travel or 0
        self.distance = _route_distance(self.sequence, self.depot_id, distances)
        return pkg

    def to_route(self) -> Route:
        depot_id = self.depot_id
        depot_start = DepotStop(position=1, location_id=depot_id, arrival=0, departure=0)
        delivery_stops = []
        for i, (pkg, (arr, dep)) in enumerate(zip(self.sequence, self.times)):
            delivery_stops.append(DeliveryStop(
                position=i + 2,
                location_id=pkg.destination_id,
                package_id=pkg.id,
                arrival=arr,
                departure=dep,
            ))
        n = len(self.sequence)
        depot_end = DepotStop(
            position=n + 2,
            location_id=depot_id,
            arrival=self.end_arrival,
            departure=self.end_arrival,
        )
        return Route(
            id=self.route_id,
            vehicle=self.vehicle,
            depot_start=depot_start,
            delivery_stops=delivery_stops,
            depot_end=depot_end,
        )


def _two_opt(state: _RouteState, distances: Dict) -> bool:
    """
    Perform one pass of 2-opt within the route.
    Returns True if any improvement was made.
    """
    n = len(state.sequence)
    if n < 2:
        return False

    improved = False
    for i in range(n - 1):
        for j in range(i + 1, n):
            new_seq = state.sequence[:i] + list(reversed(state.sequence[i:j + 1])) + state.sequence[j + 1:]
            if not _capacity_ok(new_seq, state.vehicle):
                continue
            result = _compute_times(new_seq, state.depot_id, distances)
            if result is None:
                continue
            new_dist = _route_distance(new_seq, state.depot_id, distances)
            if new_dist < state.distance - 1e-9:
                state.sequence = new_seq
                state.times, state.end_arrival = result
                state.distance = new_dist
                improved = True
    return improved


def _improve_routes(route_states: List[_RouteState], distances: Dict) -> None:
    """Run 2-opt on each route until no improvement."""
    for state in route_states:
        while _two_opt(state, distances):
            pass


def _or_opt(route_states: List[_RouteState], distances: Dict) -> bool:
    """
    Try moving single packages between routes to reduce total distance.
    Returns True if any improvement was made.
    """
    improved = False
    n_routes = len(route_states)

    for src_idx in range(n_routes):
        src = route_states[src_idx]
        if not src.sequence:
            continue

        for pkg_pos in range(len(src.sequence)):
            pkg = src.sequence[pkg_pos]

            for dst_idx in range(n_routes):
                if src_idx == dst_idx:
                    continue
                dst = route_states[dst_idx]

                result = dst.try_insert(pkg, distances)
                if result is None:
                    continue
                ins_pos, delta = result

                # Cost of removing from src
                old_src_dist = src.distance
                new_src_seq = src.sequence[:pkg_pos] + src.sequence[pkg_pos + 1:]
                if new_src_seq:
                    r = _compute_times(new_src_seq, src.depot_id, distances)
                    if r is None:
                        continue
                    new_src_dist = _route_distance(new_src_seq, src.depot_id, distances)
                else:
                    new_src_dist = _route_distance([], src.depot_id, distances)

                gain = (old_src_dist - new_src_dist) - delta
                if gain > 1e-9:
                    # Apply move
                    src.remove(pkg_pos, distances)
                    dst.insert(pkg, ins_pos, distances)
                    improved = True
                    break
            else:
                continue
            break  # restart after modification
        else:
            continue
        # re-run 2-opt on modified routes
        while _two_opt(src, distances):
            pass
        while _two_opt(route_states[dst_idx], distances):
            pass

    return improved


def plan(locations, vehicles: List[Vehicle], packages: List[Package],
         distances: Dict) -> Tuple[List[Route], Dict[str, str]]:
    """
    Main planning function. Returns (routes, undeliverable_dict).
    """
    from feasibility import check_all_packages
    feasible, undeliverable = check_all_packages(packages, vehicles, distances)

    # Sort: priority desc, then tw_close asc (earliest deadline first), then weight desc
    feasible.sort(key=lambda p: (-p.priority, p.tw_close, -p.weight_kg))

    available_vehicles = list(vehicles)
    route_states: List[_RouteState] = []
    route_counter = [0]

    def next_route_id() -> str:
        route_counter[0] += 1
        return str(route_counter[0])

    for pkg in feasible:
        best_route_idx: Optional[int] = None
        best_pos: Optional[int] = None
        best_delta = float("inf")

        # Find best insertion among existing routes
        for idx, state in enumerate(route_states):
            result = state.try_insert(pkg, distances)
            if result is None:
                continue
            pos, delta = result
            if delta < best_delta:
                best_delta = delta
                best_pos = pos
                best_route_idx = idx

        if best_route_idx is not None:
            route_states[best_route_idx].insert(pkg, best_pos, distances)
        elif available_vehicles:
            # Open new route on first available vehicle
            vehicle = available_vehicles.pop(0)
            new_state = _RouteState(vehicle, next_route_id())
            # Insert as first stop
            result = _compute_times([pkg], vehicle.depot_location_id, distances)
            if result is not None and _capacity_ok([pkg], vehicle):
                new_state.insert(pkg, 0, distances)
                route_states.append(new_state)
            else:
                # Can't even form a singleton route — put vehicle back and mark undeliverable
                available_vehicles.insert(0, vehicle)
                undeliverable[pkg.id] = "NO_VEHICLE"
        else:
            undeliverable[pkg.id] = "NO_VEHICLE"

    # Local search improvement
    _improve_routes(route_states, distances)

    or_opt_passes = 0
    while or_opt_passes < 20 and _or_opt(route_states, distances):
        _improve_routes(route_states, distances)
        or_opt_passes += 1

    # Build final Route objects (only non-empty routes)
    routes = [state.to_route() for state in route_states if state.sequence]

    return routes, undeliverable
