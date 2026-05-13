import csv
import sys
from pathlib import Path
from models import Package, Vehicle, Location, DistanceMatrix
from solver import solve

DAY_START = 8 * 60  # 08:00 in minutes since midnight


def parse_time(s: str) -> int:
    """HH:MM -> minutes since 08:00"""
    h, m = map(int, s.strip().split(':'))
    return h * 60 + m - DAY_START


def format_time(minutes: int) -> str:
    """minutes since 08:00 -> HH:MM"""
    total = minutes + DAY_START
    return f"{total // 60:02d}:{total % 60:02d}"


def read_locations(path: str) -> dict[str, Location]:
    locations = {}
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                loc = Location(location_id=row['location_id'].strip(), name=row['name'].strip())
                locations[loc.location_id] = loc
            except (KeyError, ValueError) as e:
                print(f"[WARN] Skipping invalid location row: {row} ({e})", file=sys.stderr)
    return locations


def read_vehicles(path: str, location_ids: set[str]) -> list[Vehicle]:
    vehicles = []
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                v = Vehicle(
                    vehicle_id=row['vehicle_id'].strip(),
                    max_weight_kg=float(row['max_weight_kg']),
                    max_volume_m3=float(row['max_volume_m3']),
                    depot_location_id=row['depot_location_id'].strip(),
                )
                if v.depot_location_id not in location_ids:
                    print(f"[WARN] Vehicle {v.vehicle_id} depot {v.depot_location_id} not in locations, skipping", file=sys.stderr)
                    continue
                vehicles.append(v)
            except (KeyError, ValueError) as e:
                print(f"[WARN] Skipping invalid vehicle row: {row} ({e})", file=sys.stderr)
    return vehicles


def read_packages(path: str, location_ids: set[str]) -> list[Package]:
    packages = []
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                priority_val = int(row['priority'])
                if priority_val not in (0, 1):
                    print(f"[WARN] Package {row.get('package_id')} has invalid priority {priority_val}, skipping", file=sys.stderr)
                    continue
                tw_open = parse_time(row['tw_open'])
                tw_close = parse_time(row['tw_close'])
                if tw_close <= tw_open:
                    print(f"[WARN] Package {row.get('package_id')} tw_close <= tw_open, skipping", file=sys.stderr)
                    continue
                dest_id = row['destination_id'].strip()
                if dest_id not in location_ids:
                    print(f"[WARN] Package {row.get('package_id')} destination {dest_id} not in locations, skipping", file=sys.stderr)
                    continue
                pkg = Package(
                    package_id=row['package_id'].strip(),
                    destination_id=dest_id,
                    weight_kg=float(row['weight_kg']),
                    volume_m3=float(row['volume_m3']),
                    tw_open=max(0, tw_open),
                    tw_close=tw_close,
                    service_min=int(row['service_min']),
                    priority=priority_val,
                )
                packages.append(pkg)
            except (KeyError, ValueError) as e:
                print(f"[WARN] Skipping invalid package row: {row} ({e})", file=sys.stderr)
    return packages


def read_distances(path: str, location_ids: set[str]) -> DistanceMatrix:
    dm = DistanceMatrix()
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                from_id = row['from_location_id'].strip()
                to_id = row['to_location_id'].strip()
                if from_id not in location_ids or to_id not in location_ids:
                    continue
                dm.add(from_id, to_id, float(row['distance_km']), int(row['travel_time_min']))
            except (KeyError, ValueError) as e:
                print(f"[WARN] Skipping invalid distance row: {row} ({e})", file=sys.stderr)
    return dm


def write_stops_order(path: str, routes: dict, packages_by_id: dict):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['route_id', 'vehicle_id', 'stop_position_in_order', 'location_id', 'delivered_id', 'arrival_time', 'departure_time'])
        for vehicle_id, route in sorted(routes.items()):
            schedule, _ = route.schedule()
            for pos, (pkg, (arrival, departure)) in enumerate(zip(route.stops, schedule), start=1):
                writer.writerow([
                    vehicle_id,
                    vehicle_id,
                    pos,
                    pkg.destination_id,
                    pkg.package_id,
                    format_time(arrival),
                    format_time(departure),
                ])


def write_undeliverable(path: str, undeliverable: dict[str, str]):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['package_id', 'reason'])
        for pkg_id, reason in sorted(undeliverable.items()):
            writer.writerow([pkg_id, reason])


def write_summary(path: str, routes: dict, all_vehicles: list):
    delivered_count: dict[str, int] = {}
    for v_id, route in routes.items():
        delivered_count[v_id] = len(route.stops)

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['vehicle_id', 'total_distance_km', 'total_time_min', 'packages_delivered'])
        for v in sorted(all_vehicles, key=lambda x: x.vehicle_id):
            if v.vehicle_id in routes:
                route = routes[v.vehicle_id]
                _, end_arrival = route.schedule()
                total_km = route.total_distance()
                writer.writerow([
                    v.vehicle_id,
                    f"{total_km:.2f}",
                    end_arrival,
                    len(route.stops),
                ])
            else:
                writer.writerow([v.vehicle_id, "0.00", 0, 0])


def main():
    base = Path('.')
    locations = read_locations(base / 'locations.csv')
    location_ids = set(locations.keys())
    vehicles = read_vehicles(base / 'vehicles.csv', location_ids)
    packages = read_packages(base / 'packages.csv', location_ids)
    distances = read_distances(base / 'distances.csv', location_ids)

    routes, undeliverable = solve(packages, vehicles, distances)

    write_stops_order(base / 'stops_order.csv', routes, {p.package_id: p for p in packages})
    write_undeliverable(base / 'undeliverable.csv', undeliverable)
    write_summary(base / 'summary.csv', routes, vehicles)

    print(f"Planned {sum(len(r.stops) for r in routes.values())} deliveries across {len(routes)} vehicles.")
    print(f"Undeliverable: {len(undeliverable)} packages.")


if __name__ == '__main__':
    main()
