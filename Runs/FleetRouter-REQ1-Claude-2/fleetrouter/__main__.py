#!/usr/bin/env python3
"""FleetRouter - daily route planner for courier companies."""

import csv
import argparse
import os

DEPOT_START_MIN = 480   # 08:00 in minutes since midnight
MAX_DRIVER_MIN = 480    # 8 hours = 480 minutes


def parse_time(s: str) -> int:
    """Parse HH:MM to minutes since midnight."""
    h, m = s.strip().split(':')
    return int(h) * 60 + int(m)


def fmt_time(minutes) -> str:
    """Format minutes since midnight to HH:MM."""
    return f"{int(minutes) // 60:02d}:{int(minutes) % 60:02d}"


def simulate_route(depot_id, stop_ids, packages, distances):
    """
    Simulate a vehicle route. Returns (distance_km, duration_min, stop_details).
    stop_details: list of (location_id, pkg_id, arrival_min, departure_min)
    Raises ValueError with reason code if route is infeasible.
    """
    loc = depot_id
    time = DEPOT_START_MIN
    total_dist = 0.0
    details = []

    for pid in stop_ids:
        pkg = packages[pid]
        dest = pkg['destination_id']
        edge = distances.get((loc, dest))
        if edge is None:
            raise ValueError('UNREACHABLE')

        arrival = time + edge['travel_time_min']
        tw_open = parse_time(pkg['tw_open'])
        tw_close = parse_time(pkg['tw_close'])
        service_start = max(arrival, tw_open)

        if service_start > tw_close:
            raise ValueError('TIME_WINDOW')

        departure = service_start + pkg['service_min']
        total_dist += edge['distance_km']
        details.append((dest, pid, arrival, departure))
        time = departure
        loc = dest

    if stop_ids:
        edge = distances.get((loc, depot_id))
        if edge is None:
            raise ValueError('UNREACHABLE')
        total_dist += edge['distance_km']
        duration = time + edge['travel_time_min'] - DEPOT_START_MIN
    else:
        duration = 0

    if duration > MAX_DRIVER_MIN:
        raise ValueError('MAX_DRIVER_TIME')

    return total_dist, duration, details


def two_opt(route, depot_id, packages, distances):
    """2-opt local search to minimize route distance then duration."""
    if len(route) < 3:
        return route
    try:
        best_dist, best_dur, _ = simulate_route(depot_id, route, packages, distances)
    except ValueError:
        return route

    best = route[:]
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                try:
                    d, t, _ = simulate_route(depot_id, candidate, packages, distances)
                    if d < best_dist - 1e-9 or (abs(d - best_dist) < 1e-9 and t < best_dur):
                        best_dist, best_dur, best = d, t, candidate
                        improved = True
                        break
                except ValueError:
                    pass
            if improved:
                break
    return best


def main():
    ap = argparse.ArgumentParser(description='FleetRouter courier route planner')
    ap.add_argument('--input', required=True, metavar='DIR')
    ap.add_argument('--output', required=True, metavar='DIR')
    args = ap.parse_args()

    in_dir, out_dir = args.input, args.output
    os.makedirs(out_dir, exist_ok=True)

    def load_dict(fname, key):
        with open(os.path.join(in_dir, fname), newline='') as f:
            return {row[key]: dict(row) for row in csv.DictReader(f)}

    def load_list(fname):
        with open(os.path.join(in_dir, fname), newline='') as f:
            return [dict(row) for row in csv.DictReader(f)]

    locations = load_dict('locations.csv', 'location_id')
    vehicles_raw = load_dict('vehicles.csv', 'vehicle_id')
    packages_raw = load_dict('packages.csv', 'package_id')
    distances_rows = load_list('distances.csv')

    distances = {
        (r['from_location_id'], r['to_location_id']): {
            'distance_km': float(r['distance_km']),
            'travel_time_min': int(r['travel_time_min'])
        }
        for r in distances_rows
    }

    undeliverable = {}

    # Validate and build vehicles (exclude those with unknown depot)
    vehicles = {}
    for vid, v in vehicles_raw.items():
        if v['depot_location_id'] in locations:
            vehicles[vid] = {
                'max_weight_kg': float(v['max_weight_kg']),
                'max_volume_m3': float(v['max_volume_m3']),
                'depot_location_id': v['depot_location_id'],
                'curr_weight': 0.0,
                'curr_volume': 0.0,
                'route': []
            }

    # Validate and build packages
    packages = {}
    for pid, p in packages_raw.items():
        if p['destination_id'] not in locations:
            undeliverable[pid] = 'UNREACHABLE'
            continue
        try:
            tw_open = parse_time(p['tw_open'])
            tw_close = parse_time(p['tw_close'])
        except Exception:
            undeliverable[pid] = 'TIME_WINDOW'
            continue
        if tw_open >= tw_close:
            undeliverable[pid] = 'TIME_WINDOW'
            continue
        packages[pid] = {
            'destination_id': p['destination_id'],
            'weight_kg': float(p['weight_kg']),
            'volume_m3': float(p['volume_m3']),
            'tw_open': p['tw_open'],
            'tw_close': p['tw_close'],
            'service_min': int(p['service_min']),
            'priority': int(p['priority'])
        }

    # Check global reachability: at least one depot must connect both ways
    depots = {v['depot_location_id'] for v in vehicles.values()}
    for pid in list(packages):
        dest = packages[pid]['destination_id']
        if not any(
            (dep, dest) in distances and (dest, dep) in distances
            for dep in depots
        ):
            undeliverable[pid] = 'UNREACHABLE'
            del packages[pid]

    # Sort: priority=1 first, then by earliest time-window close (most urgent first)
    ordered = sorted(
        packages,
        key=lambda p: (-packages[p]['priority'], parse_time(packages[p]['tw_close']))
    )

    _reason_priority = {'UNREACHABLE': 4, 'TIME_WINDOW': 3, 'MAX_DRIVER_TIME': 2, 'NO_VEHICLE': 1}

    # Assign packages via cheapest insertion
    for pid in ordered:
        pkg = packages[pid]
        best_v, best_pos, best_dist, best_dur = None, None, None, None
        routing_reasons = []

        for vid, v in vehicles.items():
            if v['curr_weight'] + pkg['weight_kg'] > v['max_weight_kg']:
                continue
            if v['curr_volume'] + pkg['volume_m3'] > v['max_volume_m3']:
                continue

            pos_best_dist, pos_best_dur, pos_best = None, None, None
            pos_fail = 'NO_VEHICLE'

            for pos in range(len(v['route']) + 1):
                candidate = v['route'][:pos] + [pid] + v['route'][pos:]
                try:
                    d, t, _ = simulate_route(v['depot_location_id'], candidate, packages, distances)
                    if (pos_best_dist is None
                            or d < pos_best_dist - 1e-9
                            or (abs(d - pos_best_dist) < 1e-9 and t < pos_best_dur)):
                        pos_best_dist, pos_best_dur, pos_best = d, t, pos
                except ValueError as e:
                    reason = str(e)
                    if _reason_priority.get(reason, 0) > _reason_priority.get(pos_fail, 0):
                        pos_fail = reason

            if pos_best is None:
                routing_reasons.append(pos_fail)
            elif (best_dist is None
                  or pos_best_dist < best_dist - 1e-9
                  or (abs(pos_best_dist - best_dist) < 1e-9 and pos_best_dur < best_dur)):
                best_v, best_pos = vid, pos_best
                best_dist, best_dur = pos_best_dist, pos_best_dur

        if best_v is None:
            # Determine the rejection reason
            if not vehicles:
                reason = 'NO_VEHICLE'
            elif not any(
                v['curr_weight'] + pkg['weight_kg'] <= v['max_weight_kg']
                for v in vehicles.values()
            ):
                reason = 'CAPACITY_WEIGHT'
            elif not any(
                v['curr_weight'] + pkg['weight_kg'] <= v['max_weight_kg']
                and v['curr_volume'] + pkg['volume_m3'] <= v['max_volume_m3']
                for v in vehicles.values()
            ):
                reason = 'CAPACITY_VOLUME'
            elif 'UNREACHABLE' in routing_reasons:
                reason = 'UNREACHABLE'
            elif 'TIME_WINDOW' in routing_reasons:
                reason = 'TIME_WINDOW'
            elif 'MAX_DRIVER_TIME' in routing_reasons:
                reason = 'MAX_DRIVER_TIME'
            else:
                reason = 'NO_VEHICLE'
            undeliverable[pid] = reason
        else:
            v = vehicles[best_v]
            v['route'].insert(best_pos, pid)
            v['curr_weight'] += pkg['weight_kg']
            v['curr_volume'] += pkg['volume_m3']

    # 2-opt route optimization
    for v in vehicles.values():
        if len(v['route']) >= 3:
            v['route'] = two_opt(v['route'], v['depot_location_id'], packages, distances)

    # Build output rows
    stops_rows = []
    summary_rows = []

    for vid, v in vehicles.items():
        route = v['route']
        depot = v['depot_location_id']

        if not route:
            summary_rows.append({
                'vehicle_id': vid,
                'total_distance_km': '0.00',
                'total_time_min': '0',
                'packages_delivered': '0'
            })
            continue

        dist, duration, details = simulate_route(depot, route, packages, distances)
        route_id = f"route_{vid}"

        for i, (loc_id, pkg_id, arr, dep) in enumerate(details, 1):
            stops_rows.append({
                'route_id': route_id,
                'vehicle_id': vid,
                'stop_position_in_order': i,
                'location_id': loc_id,
                'delivered_id': pkg_id,
                'arrival_time': fmt_time(arr),
                'departure_time': fmt_time(dep)
            })

        summary_rows.append({
            'vehicle_id': vid,
            'total_distance_km': f"{dist:.2f}",
            'total_time_min': str(int(duration)),
            'packages_delivered': str(len(route))
        })

    def write_csv(fname, fieldnames, rows):
        with open(os.path.join(out_dir, fname), 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    write_csv(
        'stops_order.csv',
        ['route_id', 'vehicle_id', 'stop_position_in_order', 'location_id',
         'delivered_id', 'arrival_time', 'departure_time'],
        stops_rows
    )

    write_csv(
        'undeliverable.csv',
        ['package_id', 'reason'],
        [{'package_id': p, 'reason': r} for p, r in sorted(undeliverable.items())]
    )

    write_csv(
        'summary.csv',
        ['vehicle_id', 'total_distance_km', 'total_time_min', 'packages_delivered'],
        summary_rows
    )


if __name__ == '__main__':
    main()
