"""VRPTW solver: greedy insertion with 2-opt improvement and priority handling."""
from __future__ import annotations

import math
from typing import Optional
from models import Package, Vehicle, Route, DeliveryStop, UndeliverableEntry

MAX_DRIVER_MINUTES = 480  # 8 hours


def _travel(frm: str, to: str, travel_min: dict) -> Optional[float]:
    return travel_min.get((frm, to))


def _dist(frm: str, to: str, distance_km: dict) -> float:
    return distance_km.get((frm, to), 0.0)


def _compute_times(depot: str, stops: list[Package], travel_min: dict
                   ) -> Optional[list[tuple[int, int]]]:
    """Return list of (arrival, departure) pairs for each stop.
    Returns None if any time window is violated."""
    current_time = 0
    current_loc = depot
    result = []
    for pkg in stops:
        tt = _travel(current_loc, pkg.destination_id, travel_min)
        if tt is None:
            return None
        arrival = current_time + int(tt)
        if arrival > pkg.tw_close:
            return None
        departure = max(arrival, pkg.tw_open) + pkg.service_min
        result.append((arrival, departure))
        current_time = departure
        current_loc = pkg.destination_id
    return result


def _route_end_arrival(depot: str, stops: list[Package],
                       times: list[tuple[int, int]], travel_min: dict) -> Optional[int]:
    if not stops:
        tt = _travel(depot, depot, travel_min)
        return 0 if tt is not None else 0
    last_loc = stops[-1].destination_id
    last_dep = times[-1][1]
    tt = _travel(last_loc, depot, travel_min)
    if tt is None:
        return None
    return last_dep + int(tt)


def _route_distance(depot: str, stops: list[Package], distance_km: dict) -> float:
    if not stops:
        return 0.0
    d = _dist(depot, stops[0].destination_id, distance_km)
    for i in range(len(stops) - 1):
        d += _dist(stops[i].destination_id, stops[i + 1].destination_id, distance_km)
    d += _dist(stops[-1].destination_id, depot, distance_km)
    return d


def _is_feasible_sequence(depot: str, packages: list[Package],
                           vehicle: Vehicle, travel_min: dict) -> bool:
    times = _compute_times(depot, packages, travel_min)
    if times is None:
        return False
    end_arrival = _route_end_arrival(depot, packages, times, travel_min)
    if end_arrival is None or end_arrival > MAX_DRIVER_MINUTES:
        return False
    total_w = sum(p.weight_kg for p in packages)
    total_v = sum(p.volume_m3 for p in packages)
    return total_w <= vehicle.max_weight_kg and total_v <= vehicle.max_volume_m3


def _best_insertion_cost(depot: str, current_stops: list[Package],
                         candidate: Package, vehicle: Vehicle,
                         distance_km: dict, travel_min: dict
                         ) -> Optional[tuple[float, int]]:
    """Find best insertion position for candidate. Returns (cost_delta, position) or None."""
    new_w = sum(p.weight_kg for p in current_stops) + candidate.weight_kg
    new_v = sum(p.volume_m3 for p in current_stops) + candidate.volume_m3
    if new_w > vehicle.max_weight_kg or new_v > vehicle.max_volume_m3:
        return None

    best_cost = None
    best_pos = None
    n = len(current_stops)

    for pos in range(n + 1):
        new_seq = current_stops[:pos] + [candidate] + current_stops[pos:]
        times = _compute_times(depot, new_seq, travel_min)
        if times is None:
            continue
        end_arr = _route_end_arrival(depot, new_seq, times, travel_min)
        if end_arr is None or end_arr > MAX_DRIVER_MINUTES:
            continue
        new_dist = _route_distance(depot, new_seq, distance_km)
        old_dist = _route_distance(depot, current_stops, distance_km)
        delta = new_dist - old_dist
        if best_cost is None or delta < best_cost:
            best_cost = delta
            best_pos = pos

    if best_cost is None:
        return None
    return (best_cost, best_pos)


def _determine_infeasible_reason(pkg: Package, vehicles: list[Vehicle],
                                 travel_min: dict,
                                 route_stops: list[list] | None = None) -> str:
    """Determine undeliverable reason for a package."""
    if not vehicles:
        return "NO_VEHICLE"

    all_exceed_weight = all(pkg.weight_kg > v.max_weight_kg for v in vehicles)
    if all_exceed_weight:
        return "CAPACITY_WEIGHT"

    all_exceed_volume = all(pkg.volume_m3 > v.max_volume_m3 for v in vehicles)
    if all_exceed_volume:
        return "CAPACITY_VOLUME"

    all_unreachable = all(
        _travel(v.depot_location_id, pkg.destination_id, travel_min) is None or
        _travel(pkg.destination_id, v.depot_location_id, travel_min) is None
        for v in vehicles
    )
    if all_unreachable:
        return "UNREACHABLE"

    all_time_window = True
    for v in vehicles:
        out = _travel(v.depot_location_id, pkg.destination_id, travel_min)
        if out is not None and int(out) <= pkg.tw_close:
            all_time_window = False
            break
    if all_time_window:
        return "TIME_WINDOW"

    all_max_driver = True
    for v in vehicles:
        out = _travel(v.depot_location_id, pkg.destination_id, travel_min)
        back = _travel(pkg.destination_id, v.depot_location_id, travel_min)
        if out is not None and back is not None:
            if int(out) + pkg.service_min + int(back) <= MAX_DRIVER_MINUTES:
                all_max_driver = False
                break
    if all_max_driver:
        return "MAX_DRIVER_TIME"

    # Package is individually feasible but couldn't fit in any route
    if route_stops is not None:
        for v_idx, v in enumerate(vehicles):
            used_w = sum(p.weight_kg for p in route_stops[v_idx])
            used_v = sum(p.volume_m3 for p in route_stops[v_idx])
            if used_w + pkg.weight_kg > v.max_weight_kg:
                return "CAPACITY_WEIGHT"
            if used_v + pkg.volume_m3 > v.max_volume_m3:
                return "CAPACITY_VOLUME"
    return "CAPACITY_WEIGHT"


def _pre_filter(packages: list[Package], vehicles: list[Vehicle],
                travel_min: dict) -> tuple[list[Package], list[UndeliverableEntry]]:
    """Mark packages that are individually infeasible as undeliverable."""
    feasible = []
    undeliverable = []

    if not vehicles:
        for pkg in packages:
            undeliverable.append(UndeliverableEntry(pkg.package_id, "NO_VEHICLE"))
        return [], undeliverable

    for pkg in packages:
        reason = None

        all_exceed_weight = all(pkg.weight_kg > v.max_weight_kg for v in vehicles)
        if all_exceed_weight:
            reason = "CAPACITY_WEIGHT"
        else:
            all_exceed_volume = all(pkg.volume_m3 > v.max_volume_m3 for v in vehicles)
            if all_exceed_volume:
                reason = "CAPACITY_VOLUME"

        if reason is None:
            all_unreachable = all(
                _travel(v.depot_location_id, pkg.destination_id, travel_min) is None or
                _travel(pkg.destination_id, v.depot_location_id, travel_min) is None
                for v in vehicles
            )
            if all_unreachable:
                reason = "UNREACHABLE"

        if reason is None:
            all_time_window = True
            for v in vehicles:
                out = _travel(v.depot_location_id, pkg.destination_id, travel_min)
                if out is not None and int(out) <= pkg.tw_close:
                    all_time_window = False
                    break
            if all_time_window:
                reason = "TIME_WINDOW"

        if reason is None:
            all_max_driver = True
            for v in vehicles:
                out = _travel(v.depot_location_id, pkg.destination_id, travel_min)
                back = _travel(pkg.destination_id, v.depot_location_id, travel_min)
                if out is not None and back is not None:
                    if int(out) + pkg.service_min + int(back) <= MAX_DRIVER_MINUTES:
                        all_max_driver = False
                        break
            if all_max_driver:
                reason = "MAX_DRIVER_TIME"

        if reason is not None:
            undeliverable.append(UndeliverableEntry(pkg.package_id, reason))
        else:
            feasible.append(pkg)

    return feasible, undeliverable


def _apply_two_opt(depot: str, stops: list[Package],
                   vehicle: Vehicle, distance_km: dict, travel_min: dict) -> list[Package]:
    """Improve a route using 2-opt. Returns improved stop sequence."""
    if len(stops) < 2:
        return stops

    improved = True
    best = list(stops)
    best_dist = _route_distance(depot, best, distance_km)

    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + list(reversed(best[i:j + 1])) + best[j + 1:]
                if not _is_feasible_sequence(depot, candidate, vehicle, travel_min):
                    continue
                new_dist = _route_distance(depot, candidate, distance_km)
                if new_dist < best_dist - 1e-9:
                    best = candidate
                    best_dist = new_dist
                    improved = True
                    break
            if improved:
                break

    return best


def _or_opt_relocate(routes: list[Route], distance_km: dict, travel_min: dict,
                     max_rounds: int = 3) -> None:
    """Try moving single stops between routes to reduce total distance.
    Uses a greedy sweep: evaluate all potential moves, execute best non-conflicting ones."""
    for _ in range(max_rounds):
        # Build candidate moves: (savings, src_idx, stop_idx, dst_idx, insert_pos)
        moves: list[tuple] = []
        for r_src_idx, r_src in enumerate(routes):
            if not r_src.stops:
                continue
            src_depot = r_src.vehicle.depot_location_id
            src_pkgs = [s.package for s in r_src.stops]
            src_dist = _route_distance(src_depot, src_pkgs, distance_km)
            for stop_idx in range(len(src_pkgs)):
                pkg = src_pkgs[stop_idx]
                new_src = src_pkgs[:stop_idx] + src_pkgs[stop_idx + 1:]
                if new_src:
                    times_new_src = _compute_times(src_depot, new_src, travel_min)
                    if times_new_src is None:
                        continue
                    end_arr = _route_end_arrival(src_depot, new_src, times_new_src, travel_min)
                    if end_arr is None or end_arr > MAX_DRIVER_MINUTES:
                        continue
                src_dist_new = _route_distance(src_depot, new_src, distance_km)
                src_delta = src_dist_new - src_dist

                for r_dst_idx, r_dst in enumerate(routes):
                    if r_dst_idx == r_src_idx:
                        continue
                    dst_depot = r_dst.vehicle.depot_location_id
                    dst_pkgs = [s.package for s in r_dst.stops]
                    result = _best_insertion_cost(
                        dst_depot, dst_pkgs, pkg, r_dst.vehicle, distance_km, travel_min
                    )
                    if result is None:
                        continue
                    delta_dst, pos = result
                    total_delta = src_delta + delta_dst
                    if total_delta < -1e-9:
                        moves.append((total_delta, r_src_idx, stop_idx, r_dst_idx, pos))

        if not moves:
            break

        # Execute moves greedily by best savings; skip conflicting routes
        moves.sort()
        used_routes: set[int] = set()
        any_moved = False
        for total_delta, r_src_idx, stop_idx, r_dst_idx, insert_pos in moves:
            if r_src_idx in used_routes or r_dst_idx in used_routes:
                continue
            r_src = routes[r_src_idx]
            r_dst = routes[r_dst_idx]
            src_depot = r_src.vehicle.depot_location_id
            dst_depot = r_dst.vehicle.depot_location_id
            src_pkgs = [s.package for s in r_src.stops]
            dst_pkgs = [s.package for s in r_dst.stops]
            pkg = src_pkgs[stop_idx]
            new_src = src_pkgs[:stop_idx] + src_pkgs[stop_idx + 1:]
            new_dst = dst_pkgs[:insert_pos] + [pkg] + dst_pkgs[insert_pos:]

            times_src = _compute_times(src_depot, new_src, travel_min) if new_src else []
            times_dst = _compute_times(dst_depot, new_dst, travel_min)
            if times_dst is None:
                continue
            end_dst = _route_end_arrival(dst_depot, new_dst, times_dst, travel_min)
            if end_dst is None or end_dst > MAX_DRIVER_MINUTES:
                continue

            end_src = _route_end_arrival(src_depot, new_src, times_src, travel_min) if new_src else 0
            r_src.stops = _build_delivery_stops(new_src, times_src)
            r_src.depot_arrival = end_src or 0
            r_dst.stops = _build_delivery_stops(new_dst, times_dst)
            r_dst.depot_arrival = end_dst
            used_routes.add(r_src_idx)
            used_routes.add(r_dst_idx)
            any_moved = True

        if not any_moved:
            break


def _build_delivery_stops(packages: list[Package],
                          times: list[tuple[int, int]]) -> list[DeliveryStop]:
    return [
        DeliveryStop(
            package=pkg,
            position=i + 1,
            arrival=arr,
            departure=dep,
        )
        for i, (pkg, (arr, dep)) in enumerate(zip(packages, times))
    ]


def solve(packages: list[Package], vehicles: list[Vehicle],
          distance_km: dict, travel_min: dict) -> tuple[list[Route], list[UndeliverableEntry]]:
    """Main solver entry point."""
    feasible, undeliverable = _pre_filter(packages, vehicles, travel_min)

    # Sort: priority desc, then tw_close asc
    feasible.sort(key=lambda p: (-p.priority, p.tw_close))

    # Initialize empty routes (one per vehicle)
    routes: list[Route] = [
        Route(route_id=i + 1, vehicle=v)
        for i, v in enumerate(vehicles)
    ]
    route_stops: list[list[Package]] = [[] for _ in vehicles]

    unassigned: list[Package] = []

    for pkg in feasible:
        best_route_idx = None
        best_pos = None
        best_delta = None

        for r_idx, route in enumerate(routes):
            depot = route.vehicle.depot_location_id
            result = _best_insertion_cost(
                depot, route_stops[r_idx], pkg, route.vehicle, distance_km, travel_min
            )
            if result is None:
                continue
            delta, pos = result
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_route_idx = r_idx
                best_pos = pos

        if best_route_idx is not None:
            route_stops[best_route_idx].insert(best_pos, pkg)
        else:
            # Priority package: try displacing non-priority stops
            if pkg.priority == 1:
                displaced = _try_displace_for_priority(
                    pkg, routes, route_stops, distance_km, travel_min
                )
                if displaced is not None:
                    r_idx, pos, removed = displaced
                    route_stops[r_idx].insert(pos, pkg)
                    unassigned.extend(removed)
                else:
                    reason = _determine_infeasible_reason(pkg, vehicles, travel_min)
                    undeliverable.append(UndeliverableEntry(pkg.package_id, reason))
            else:
                unassigned.append(pkg)

    # Try to insert unassigned (non-priority) packages
    still_unassigned = []
    for pkg in unassigned:
        best_route_idx = None
        best_pos = None
        best_delta = None

        for r_idx, route in enumerate(routes):
            depot = route.vehicle.depot_location_id
            result = _best_insertion_cost(
                depot, route_stops[r_idx], pkg, route.vehicle, distance_km, travel_min
            )
            if result is None:
                continue
            delta, pos = result
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_route_idx = r_idx
                best_pos = pos

        if best_route_idx is not None:
            route_stops[best_route_idx].insert(best_pos, pkg)
        else:
            still_unassigned.append(pkg)

    for pkg in still_unassigned:
        reason = _determine_infeasible_reason(pkg, vehicles, travel_min, route_stops)
        undeliverable.append(UndeliverableEntry(pkg.package_id, reason))

    # Apply 2-opt improvement per route
    for r_idx, route in enumerate(routes):
        depot = route.vehicle.depot_location_id
        improved = _apply_two_opt(depot, route_stops[r_idx], route.vehicle, distance_km, travel_min)
        route_stops[r_idx] = improved

    # Build final Route objects with times
    for r_idx, route in enumerate(routes):
        depot = route.vehicle.depot_location_id
        stops = route_stops[r_idx]
        times = _compute_times(depot, stops, travel_min) or []
        route.stops = _build_delivery_stops(stops, times)
        route.depot_arrival = _route_end_arrival(depot, stops, times, travel_min) or 0

    # Apply or-opt inter-route improvement
    _or_opt_relocate(routes, distance_km, travel_min)

    return routes, undeliverable


def _try_displace_for_priority(
    pkg: Package,
    routes: list[Route],
    route_stops: list[list[Package]],
    distance_km: dict,
    travel_min: dict,
) -> Optional[tuple[int, int, list[Package]]]:
    """Try to remove non-priority stops from a route to fit a priority package.
    Returns (route_idx, insert_pos, removed_packages) or None."""
    for r_idx, route in enumerate(routes):
        depot = route.vehicle.depot_location_id
        stops = route_stops[r_idx]
        non_priority_indices = [i for i, p in enumerate(stops) if p.priority == 0]
        if not non_priority_indices:
            continue

        # Try removing one non-priority stop at a time
        for remove_idx in non_priority_indices:
            reduced = stops[:remove_idx] + stops[remove_idx + 1:]
            result = _best_insertion_cost(
                depot, reduced, pkg, route.vehicle, distance_km, travel_min
            )
            if result is not None:
                _, pos = result
                removed = [stops[remove_idx]]
                route_stops[r_idx] = reduced
                return (r_idx, pos, removed)

        # Try removing two non-priority stops
        for i in range(len(non_priority_indices)):
            for j in range(i + 1, len(non_priority_indices)):
                ri, rj = non_priority_indices[i], non_priority_indices[j]
                to_remove = sorted([ri, rj], reverse=True)
                reduced = list(stops)
                removed_pkgs = []
                for idx in to_remove:
                    removed_pkgs.append(reduced.pop(idx))
                result = _best_insertion_cost(
                    depot, reduced, pkg, route.vehicle, distance_km, travel_min
                )
                if result is not None:
                    _, pos = result
                    route_stops[r_idx] = reduced
                    return (r_idx, pos, removed_pkgs)

    return None
