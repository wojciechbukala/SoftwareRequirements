from typing import Dict, List

from .models import DistanceMap
from .route import Route


def _two_opt(route: Route, distances: DistanceMap) -> Route:
    """Apply 2-opt local search to a single route.

    Uses the 'best improvement' strategy: each pass evaluates all (i, j) pairs
    and applies the reversal that yields the greatest distance reduction.
    Repeats until no improving swap exists.
    """
    if len(route.stops) < 2:
        return route

    stops = list(route.stops)
    improved = True

    while improved:
        improved = False
        best_dist = Route(route.vehicle, stops).total_distance(distances)
        best_stops = stops

        n = len(stops)
        for i in range(n - 1):
            for j in range(i + 1, n):
                candidate = stops[:i] + list(reversed(stops[i : j + 1])) + stops[j + 1 :]
                candidate_route = Route(route.vehicle, candidate)
                if not candidate_route.is_feasible(distances):
                    continue
                d = candidate_route.total_distance(distances)
                if d < best_dist - 1e-9:
                    best_dist = d
                    best_stops = candidate
                    improved = True

        stops = best_stops

    return Route(route.vehicle, stops)


def _try_relocate(routes: Dict[str, Route], distances: DistanceMap) -> bool:
    """Attempt to move one package from one route to another for a net distance gain.

    Returns True and applies the move if an improving relocate is found.
    Verifies feasibility of both the donor route (after removal) and the
    recipient route (after insertion) before accepting.
    """
    vehicle_ids = list(routes.keys())

    for src_vid in vehicle_ids:
        src_route = routes[src_vid]
        if not src_route.stops:
            continue

        for i, pkg in enumerate(src_route.stops):
            src_stops_without = src_route.stops[:i] + src_route.stops[i + 1 :]
            src_trimmed = Route(src_route.vehicle, src_stops_without)

            # Removing a package can increase waiting time for remaining stops,
            # so we must verify the trimmed route is still feasible.
            if src_stops_without and not src_trimmed.is_feasible(distances):
                continue

            src_dist_gain = src_route.total_distance(distances) - src_trimmed.total_distance(distances)

            for dst_vid in vehicle_ids:
                if dst_vid == src_vid:
                    continue
                dst_route = routes[dst_vid]

                for j in range(len(dst_route.stops) + 1):
                    dst_stops_with = dst_route.stops[:j] + [pkg] + dst_route.stops[j:]
                    dst_extended = Route(dst_route.vehicle, dst_stops_with)

                    if not dst_extended.is_feasible(distances):
                        continue

                    dst_dist_cost = dst_extended.total_distance(distances) - dst_route.total_distance(distances)

                    if src_dist_gain - dst_dist_cost > 1e-9:
                        routes[src_vid] = src_trimmed
                        routes[dst_vid] = dst_extended
                        return True

    return False


def optimize_routes(routes: Dict[str, Route], distances: DistanceMap) -> Dict[str, Route]:
    """Minimize total fleet distance using 2-opt (per route) and relocate (cross-route).

    Applies 2-opt to every route first, then alternates relocate passes with
    2-opt until no further improvement is possible.
    """
    for vid in list(routes.keys()):
        routes[vid] = _two_opt(routes[vid], distances)

    improved = True
    while improved:
        improved = _try_relocate(routes, distances)
        if improved:
            for vid in list(routes.keys()):
                routes[vid] = _two_opt(routes[vid], distances)

    return routes
