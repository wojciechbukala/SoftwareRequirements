from typing import Optional
from models import Package, Vehicle, DistanceMatrix

MAX_DRIVER_MIN = 480
_INF = float('inf')


class Route:
    def __init__(self, vehicle: Vehicle, distances: DistanceMatrix):
        self.vehicle = vehicle
        self.distances = distances
        self.depot_id = vehicle.depot_location_id
        self.stops: list[Package] = []
        self._total_weight: float = 0.0
        self._total_volume: float = 0.0

    def _schedule_for(self, stops: list[Package]) -> Optional[tuple[list[tuple[int, int]], int]]:
        """Compute arrival/departure for a given stop sequence. Returns None if infeasible."""
        schedule = []
        t = 0
        prev = self.depot_id
        dm = self.distances

        for pkg in stops:
            travel = dm.get_min(prev, pkg.destination_id)
            if travel is None:
                return None
            arrival = t + travel
            if arrival > pkg.tw_close:
                return None
            departure = (arrival if arrival >= pkg.tw_open else pkg.tw_open) + pkg.service_min
            schedule.append((arrival, departure))
            t = departure
            prev = pkg.destination_id

        back = dm.get_min(prev, self.depot_id)
        if back is None:
            return None
        end = t + back
        if end > MAX_DRIVER_MIN:
            return None

        return schedule, end

    def _distance_for(self, stops: list[Package]) -> float:
        total = 0.0
        prev = self.depot_id
        dm = self.distances
        for pkg in stops:
            d = dm.get_km(prev, pkg.destination_id)
            if d is None:
                return _INF
            total += d
            prev = pkg.destination_id
        d = dm.get_km(prev, self.depot_id)
        return total + d if d is not None else _INF

    def try_insert(self, package: Package, position: int) -> Optional[float]:
        if self._total_weight + package.weight_kg > self.vehicle.max_weight_kg + 1e-9:
            return None
        if self._total_volume + package.volume_m3 > self.vehicle.max_volume_m3 + 1e-9:
            return None

        stops = self.stops
        n = len(stops)
        dm = self.distances

        prev_loc = stops[position - 1].destination_id if position > 0 else self.depot_id
        next_loc = stops[position].destination_id if position < n else self.depot_id

        d_pn = dm.get_km(prev_loc, package.destination_id)
        d_nd = dm.get_km(package.destination_id, next_loc)
        if d_pn is None or d_nd is None:
            return None

        d_orig = dm.get_km(prev_loc, next_loc) or 0.0
        cost = d_pn + d_nd - d_orig

        new_stops = stops[:position] + [package] + stops[position:]
        if self._schedule_for(new_stops) is None:
            return None

        return cost

    def insert(self, package: Package, position: int):
        self.stops.insert(position, package)
        self._total_weight += package.weight_kg
        self._total_volume += package.volume_m3

    def remove(self, index: int) -> Package:
        pkg = self.stops.pop(index)
        self._total_weight -= pkg.weight_kg
        self._total_volume -= pkg.volume_m3
        return pkg

    def total_distance(self) -> float:
        return self._distance_for(self.stops)

    def schedule(self) -> tuple[list[tuple[int, int]], int]:
        result = self._schedule_for(self.stops)
        return result if result is not None else ([], 0)

    def two_opt(self):
        """2-opt improvement until no gain or 50 passes."""
        stops = self.stops
        n = len(stops)
        if n < 2:
            return
        for _ in range(50):
            improved = False
            best_gain = 1e-9
            best_i = best_j = -1
            cur_dist = self._distance_for(stops)
            for i in range(n - 1):
                for j in range(i + 1, n):
                    candidate = stops[:i] + stops[i:j + 1][::-1] + stops[j + 1:]
                    new_dist = self._distance_for(candidate)
                    if new_dist < cur_dist - best_gain:
                        # Also verify timing
                        if self._schedule_for(candidate) is not None:
                            best_gain = cur_dist - new_dist
                            best_i, best_j = i, j
                            improved = True
            if improved:
                self.stops = stops[:best_i] + stops[best_i:best_j + 1][::-1] + stops[best_j + 1:]
                stops = self.stops
                cur_dist -= best_gain
            else:
                break


def _undeliverable_reason(package: Package, vehicles: list[Vehicle], distances: DistanceMatrix) -> Optional[str]:
    if not vehicles:
        return "NO_VEHICLE"

    all_unreachable = True
    all_cap_weight = True
    all_cap_volume = True
    all_max_driver = True
    all_time_window = True

    for v in vehicles:
        dep = v.depot_location_id
        out_t = distances.get_min(dep, package.destination_id)
        in_t = distances.get_min(package.destination_id, dep)

        if out_t is None or in_t is None:
            continue
        all_unreachable = False

        if package.weight_kg <= v.max_weight_kg + 1e-9:
            all_cap_weight = False
        if package.volume_m3 <= v.max_volume_m3 + 1e-9:
            all_cap_volume = False
        if out_t <= package.tw_close:
            all_time_window = False
        if out_t + package.service_min + in_t <= MAX_DRIVER_MIN:
            all_max_driver = False

    if all_unreachable:
        return "UNREACHABLE"
    if all_cap_weight:
        return "CAPACITY_WEIGHT"
    if all_cap_volume:
        return "CAPACITY_VOLUME"
    if all_max_driver:
        return "MAX_DRIVER_TIME"
    if all_time_window:
        return "TIME_WINDOW"
    return None


def solve(
    packages: list[Package],
    vehicles: list[Vehicle],
    distances: DistanceMatrix,
) -> tuple[dict[str, Route], dict[str, str]]:
    undeliverable: dict[str, str] = {}
    feasible: list[Package] = []

    for pkg in packages:
        reason = _undeliverable_reason(pkg, vehicles, distances)
        if reason:
            undeliverable[pkg.package_id] = reason
        else:
            feasible.append(pkg)

    routes = {v.vehicle_id: Route(v, distances) for v in vehicles}

    # Priority DESC, then deadline ASC for earliest-deadline-first among same priority
    sorted_pkgs = sorted(feasible, key=lambda p: (-p.priority, p.tw_close))

    for pkg in sorted_pkgs:
        best_vid = None
        best_pos = None
        best_cost = _INF

        for v_id, route in routes.items():
            n = len(route.stops)
            for pos in range(n + 1):
                cost = route.try_insert(pkg, pos)
                if cost is not None and cost < best_cost:
                    best_cost = cost
                    best_vid = v_id
                    best_pos = pos

        if best_vid is not None:
            routes[best_vid].insert(pkg, best_pos)
        else:
            undeliverable[pkg.package_id] = "NO_VEHICLE"

    for route in routes.values():
        route.two_opt()

    _or_opt(routes, max_passes=3)

    active = {v_id: r for v_id, r in routes.items() if r.stops}
    return active, undeliverable


def _or_opt(routes: dict[str, Route], max_passes: int = 3):
    """Relocate single packages between routes; limited passes for performance."""
    route_list = list(routes.values())
    n_routes = len(route_list)

    for _ in range(max_passes):
        any_improved = False
        for src in route_list:
            i = 0
            while i < len(src.stops):
                pkg = src.stops[i]
                d_before = src.total_distance()
                src.remove(i)
                d_after = src.total_distance()
                saved = d_before - d_after

                best_gain = 1e-9
                best_dst = None
                best_pos = None

                for dst in route_list:
                    if dst is src:
                        continue
                    m = len(dst.stops)
                    for pos in range(m + 1):
                        cost = dst.try_insert(pkg, pos)
                        if cost is not None:
                            gain = saved - cost
                            if gain > best_gain:
                                best_gain = gain
                                best_dst = dst
                                best_pos = pos

                if best_dst is not None:
                    best_dst.insert(pkg, best_pos)
                    any_improved = True
                    # Don't increment i; next package shifted into position i
                else:
                    src.stops.insert(i, pkg)
                    src._total_weight += pkg.weight_kg
                    src._total_volume += pkg.volume_m3
                    i += 1

        if not any_improved:
            break
