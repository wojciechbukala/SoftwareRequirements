#!/usr/bin/env python3
"""FleetRouter - Daily route planning for courier companies."""

import argparse
import csv
import os
import sys

START_TIME = 8 * 60       # 08:00 in minutes from midnight
MAX_DRIVER_TIME = 8 * 60  # 480 minutes (8 hours)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_time(s):
    """Parse 'HH:MM' to minutes since midnight."""
    h, m = s.strip().split(':')
    return int(h) * 60 + int(m)


def format_time(minutes):
    """Format minutes since midnight to 'HH:MM'."""
    return f"{int(minutes) // 60:02d}:{int(minutes) % 60:02d}"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class Package:
    __slots__ = ('id', 'location_id', 'weight', 'volume',
                 'time_open', 'time_close', 'service_duration', 'priority')

    def __init__(self, pkg_id, location_id, weight, volume,
                 time_open, time_close, service_duration, priority):
        self.id = pkg_id
        self.location_id = location_id
        self.weight = float(weight)
        self.volume = float(volume)
        self.time_open = int(time_open)
        self.time_close = int(time_close)
        self.service_duration = int(service_duration)
        self.priority = priority


class Vehicle:
    __slots__ = ('id', 'max_weight', 'max_volume', 'depot_id')

    def __init__(self, v_id, max_weight, max_volume, depot_id):
        self.id = v_id
        self.max_weight = float(max_weight)
        self.max_volume = float(max_volume)
        self.depot_id = depot_id


# ---------------------------------------------------------------------------
# Routing primitives
# ---------------------------------------------------------------------------

def get_dist(distances, from_loc, to_loc):
    """Return (distance_km, travel_time_min) or None if entry missing.
    Same-location travel is free."""
    if from_loc == to_loc:
        return (0.0, 0)
    return distances.get((from_loc, to_loc))


def simulate_route(vehicle, packages, distances):
    """Simulate a vehicle route starting and ending at the depot (08:00 departure).

    Returns (stops, total_dist_km, total_duration_min) or None if any required
    distance entry is missing.

    stops is a list of (location_id, package_or_None, arrival_min, departure_min).
    """
    time = START_TIME
    loc = vehicle.depot_id
    total_dist = 0.0
    stops = [(loc, None, time, time)]

    for pkg in packages:
        d = get_dist(distances, loc, pkg.location_id)
        if d is None:
            return None
        dist, travel = d

        arrival = time + travel
        # Wait at location if early
        effective = max(arrival, pkg.time_open)
        departure = effective + pkg.service_duration

        stops.append((pkg.location_id, pkg, effective, departure))
        total_dist += dist
        time = departure
        loc = pkg.location_id

    # Return to depot
    d = get_dist(distances, loc, vehicle.depot_id)
    if d is None:
        return None
    dist, travel = d
    return_time = time + travel
    total_dist += dist
    stops.append((vehicle.depot_id, None, return_time, return_time))

    duration = return_time - START_TIME
    return stops, total_dist, duration


def stops_feasible(stops, duration):
    """Return True if all time windows are met and duration <= 8 h."""
    if duration > MAX_DRIVER_TIME:
        return False
    for _, pkg, arrival, _ in stops:
        if pkg is not None and arrival > pkg.time_close:
            return False
    return True


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

def _open_csv(path):
    return open(path, newline='', encoding='utf-8')


def load_locations(path):
    locs = {}
    with _open_csv(path) as f:
        for row in csv.DictReader(f):
            locs[row['location_id'].strip()] = row['name'].strip()
    return locs


def load_distances(path):
    dists = {}
    with _open_csv(path) as f:
        for row in csv.DictReader(f):
            key = (row['from_location_id'].strip(), row['to_location_id'].strip())
            dists[key] = (float(row['distance_km']), int(row['travel_time_min']))
    return dists


def load_packages(path, locations):
    packages = []
    undeliverable = []
    with _open_csv(path) as f:
        for row in csv.DictReader(f):
            pid = row['package_id'].strip()
            loc_id = row['location_id'].strip()

            if loc_id not in locations:
                undeliverable.append((pid, 'UNREACHABLE'))
                continue

            try:
                time_open = parse_time(row['time_open'])
                time_close = parse_time(row['time_close'])
            except (ValueError, KeyError):
                undeliverable.append((pid, 'TIME_WINDOW'))
                continue

            if time_open >= time_close:
                undeliverable.append((pid, 'TIME_WINDOW'))
                continue

            priority_val = row.get('priority', '').strip().lower()
            priority = priority_val in ('true', '1', 'yes', 'y')

            packages.append(Package(
                pkg_id=pid,
                location_id=loc_id,
                weight=row['weight'],
                volume=row['volume'],
                time_open=time_open,
                time_close=time_close,
                service_duration=row['service_duration'],
                priority=priority,
            ))
    return packages, undeliverable


def load_vehicles(path, locations):
    vehicles = []
    with _open_csv(path) as f:
        for row in csv.DictReader(f):
            depot_id = row['depot_location_id'].strip()
            if depot_id not in locations:
                continue  # excluded; no matching package-like output for vehicles
            vehicles.append(Vehicle(
                v_id=row['vehicle_id'].strip(),
                max_weight=row['max_weight'],
                max_volume=row['max_volume'],
                depot_id=depot_id,
            ))
    return vehicles


# ---------------------------------------------------------------------------
# Route planning
# ---------------------------------------------------------------------------

def _determine_reason(pkg, routes, distances):
    """Identify why a package could not be assigned to any vehicle."""
    if not routes:
        return 'NO_VEHICLE'

    # 1. Weight capacity
    weight_ok = [r for r in routes.values()
                 if r['weight_used'] + pkg.weight <= r['vehicle'].max_weight]
    if not weight_ok:
        return 'CAPACITY_WEIGHT'

    # 2. Volume capacity
    vol_ok = [r for r in weight_ok
              if r['volume_used'] + pkg.volume <= r['vehicle'].max_volume]
    if not vol_ok:
        return 'CAPACITY_VOLUME'

    # 3–5. Try every insertion position to classify the blocker
    reachable = False
    time_ok_seen = False
    driver_ok_seen = False

    for r in vol_ok:
        v = r['vehicle']
        pkgs = r['packages']
        for pos in range(len(pkgs) + 1):
            new_pkgs = pkgs[:pos] + [pkg] + pkgs[pos:]
            result = simulate_route(v, new_pkgs, distances)
            if result is None:
                continue
            reachable = True
            stops, _, duration = result
            for _, p, arrival, _ in stops:
                if p is pkg:
                    if arrival <= pkg.time_close:
                        time_ok_seen = True
                        if duration <= MAX_DRIVER_TIME:
                            driver_ok_seen = True
                    break

    if not reachable:
        return 'UNREACHABLE'
    if not time_ok_seen:
        return 'TIME_WINDOW'
    if not driver_ok_seen:
        return 'MAX_DRIVER_TIME'
    return 'NO_VEHICLE'


def plan_routes(packages, vehicles, distances):
    """Assign packages to vehicles using a greedy cheapest-insertion heuristic.

    Priority packages are considered before non-priority ones.
    Among feasible insertions the one that minimises (delta_distance, delta_duration)
    is chosen, implementing the spec's optimisation objective.
    """
    routes = {
        v.id: {
            'vehicle': v,
            'packages': [],
            'weight_used': 0.0,
            'volume_used': 0.0,
        }
        for v in vehicles
    }
    undeliverable = []

    # Priority-first ordering; stable sort within each group preserves input order
    priority_pkgs = [p for p in packages if p.priority]
    normal_pkgs = [p for p in packages if not p.priority]
    ordered = priority_pkgs + normal_pkgs

    for pkg in ordered:
        best_vid = None
        best_pos = None
        best_cost = (float('inf'), float('inf'))  # (delta_dist, delta_dur)

        for v_id, route in routes.items():
            v = route['vehicle']
            pkgs = route['packages']

            if route['weight_used'] + pkg.weight > v.max_weight:
                continue
            if route['volume_used'] + pkg.volume > v.max_volume:
                continue

            cur = simulate_route(v, pkgs, distances)
            cur_dist = cur[1] if cur else 0.0
            cur_dur = cur[2] if cur else 0

            for pos in range(len(pkgs) + 1):
                new_pkgs = pkgs[:pos] + [pkg] + pkgs[pos:]
                result = simulate_route(v, new_pkgs, distances)
                if result is None:
                    continue
                stops, new_dist, new_dur = result
                if not stops_feasible(stops, new_dur):
                    continue

                cost = (new_dist - cur_dist, new_dur - cur_dur)
                if cost < best_cost:
                    best_cost = cost
                    best_vid = v_id
                    best_pos = pos

        if best_vid is not None:
            route = routes[best_vid]
            route['packages'].insert(best_pos, pkg)
            route['weight_used'] += pkg.weight
            route['volume_used'] += pkg.volume
        else:
            reason = _determine_reason(pkg, routes, distances)
            undeliverable.append((pkg.id, reason))

    return routes, undeliverable


def optimize_2opt(routes, distances):
    """Apply 2-opt improvement to each vehicle's route."""
    for route in routes.values():
        pkgs = route['packages']
        if len(pkgs) < 2:
            continue

        improved = True
        while improved:
            improved = False
            cur = simulate_route(route['vehicle'], pkgs, distances)
            if cur is None:
                break
            cur_dist, cur_dur = cur[1], cur[2]
            n = len(pkgs)

            found = False
            for i in range(n - 1):
                if found:
                    break
                for j in range(i + 1, n):
                    candidate = pkgs[:i] + pkgs[i:j + 1][::-1] + pkgs[j + 1:]
                    res = simulate_route(route['vehicle'], candidate, distances)
                    if res is None:
                        continue
                    stops, nd, ndu = res
                    if not stops_feasible(stops, ndu):
                        continue
                    if (nd, ndu) < (cur_dist, cur_dur):
                        pkgs = candidate
                        cur_dist, cur_dur = nd, ndu
                        improved = True
                        found = True
                        break

        route['packages'] = pkgs


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------

def write_output(routes, undeliverable, output_dir, distances):
    os.makedirs(output_dir, exist_ok=True)

    stops_rows = []
    summary_rows = []
    route_id = 0

    for v_id, route in routes.items():
        pkgs = route['packages']
        if not pkgs:
            continue

        route_id += 1
        v = route['vehicle']
        result = simulate_route(v, pkgs, distances)
        if result is None:
            continue
        stops, total_dist, total_dur = result

        for order, (loc_id, pkg, arrival, departure) in enumerate(stops, start=1):
            stops_rows.append({
                'route_id': route_id,
                'vehicle_id': v_id,
                'stop_order': order,
                'location_id': loc_id,
                'package_id': pkg.id if pkg is not None else '',
                'arrival_time': format_time(arrival),
                'departure_time': format_time(departure),
            })

        summary_rows.append({
            'vehicle_id': v_id,
            'total_distance_km': f"{total_dist:.2f}",
            'total_duration_min': int(total_dur),
            'num_packages_delivered': len(pkgs),
        })

    _write_csv(
        os.path.join(output_dir, 'stops_order.csv'),
        ['route_id', 'vehicle_id', 'stop_order', 'location_id',
         'package_id', 'arrival_time', 'departure_time'],
        stops_rows,
    )
    _write_csv(
        os.path.join(output_dir, 'undeliverable.csv'),
        ['package_id', 'reason'],
        [{'package_id': pid, 'reason': r} for pid, r in undeliverable],
    )
    _write_csv(
        os.path.join(output_dir, 'summary.csv'),
        ['vehicle_id', 'total_distance_km', 'total_duration_min', 'num_packages_delivered'],
        summary_rows,
    )


def _write_csv(path, fieldnames, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog='fleetrouter',
        description='FleetRouter: daily route planner for courier companies.',
    )
    parser.add_argument('--input', required=True, metavar='<dir>',
                        help='Directory containing input CSV files')
    parser.add_argument('--output', required=True, metavar='<dir>',
                        help='Directory for output CSV files')
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    try:
        locations = load_locations(os.path.join(input_dir, 'locations.csv'))
        distances = load_distances(os.path.join(input_dir, 'distances.csv'))
        packages, early_undeliverable = load_packages(
            os.path.join(input_dir, 'packages.csv'), locations)
        vehicles = load_vehicles(os.path.join(input_dir, 'vehicles.csv'), locations)
    except FileNotFoundError as e:
        print(f"Error: input file not found: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading input data: {e}", file=sys.stderr)
        sys.exit(1)

    routes, routing_undeliverable = plan_routes(packages, vehicles, distances)
    optimize_2opt(routes, distances)

    all_undeliverable = early_undeliverable + routing_undeliverable
    write_output(routes, all_undeliverable, output_dir, distances)


if __name__ == '__main__':
    main()
