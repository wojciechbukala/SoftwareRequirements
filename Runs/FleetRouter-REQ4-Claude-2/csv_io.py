import csv
import sys
from typing import Optional
from models import Location, Package, Vehicle, UndeliverableEntry


def _parse_time(value: str, field_name: str, row_id: str) -> Optional[int]:
    """Parse HH:MM time string to minutes since 08:00."""
    value = value.strip()
    parts = value.split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    return (h * 60 + m) - 8 * 60


def _fmt_time(minutes_since_8: int) -> str:
    """Format minutes since 08:00 as HH:MM."""
    total_minutes = 8 * 60 + minutes_since_8
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h:02d}:{m:02d}"


def read_locations(path: str) -> dict[str, Location]:
    locations = {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                loc_id = row["location_id"].strip()
                locations[loc_id] = Location(
                    location_id=loc_id,
                    name=row["name"].strip(),
                )
    except FileNotFoundError:
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    return locations


def read_distances(path: str) -> dict[tuple, float]:
    """Returns (from_id, to_id) -> distance_km and (from_id, to_id) -> travel_min."""
    distance_km: dict[tuple, float] = {}
    travel_min: dict[tuple, float] = {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                frm = row["from_location_id"].strip()
                to = row["to_location_id"].strip()
                distance_km[(frm, to)] = float(row["distance_km"])
                travel_min[(frm, to)] = float(row["travel_time_min"])
    except FileNotFoundError:
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    return distance_km, travel_min


def read_packages(path: str) -> tuple[list, list]:
    """Returns (valid_packages, skipped_ids)."""
    packages = []
    skipped = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pkg_id = row["package_id"].strip()
                try:
                    priority_raw = int(row["priority"].strip())
                    if priority_raw not in (0, 1):
                        raise ValueError
                    tw_open = _parse_time(row["tw_open"].strip(), "tw_open", pkg_id)
                    tw_close = _parse_time(row["tw_close"].strip(), "tw_close", pkg_id)
                    if tw_open is None or tw_close is None:
                        raise ValueError
                    packages.append(Package(
                        package_id=pkg_id,
                        destination_id=row["destination_id"].strip(),
                        weight_kg=float(row["weight_kg"]),
                        volume_m3=float(row["volume_m3"]),
                        tw_open=tw_open,
                        tw_close=tw_close,
                        service_min=int(row["service_min"]),
                        priority=priority_raw,
                    ))
                except (ValueError, KeyError):
                    skipped.append(pkg_id)
    except FileNotFoundError:
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    return packages, skipped


def read_vehicles(path: str) -> list:
    vehicles = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                vehicles.append(Vehicle(
                    vehicle_id=row["vehicle_id"].strip(),
                    max_weight_kg=float(row["max_weight_kg"]),
                    max_volume_m3=float(row["max_volume_m3"]),
                    depot_location_id=row["depot_location_id"].strip(),
                ))
    except FileNotFoundError:
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    return vehicles


def write_stops_order(path: str, routes: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["route_id", "vehicle_id", "stop_position_in_order",
                         "location_id", "delivered_id", "arrival_time", "departure_time"])
        for route in routes:
            if not route.stops:
                continue
            vid = route.vehicle.vehicle_id
            rid = route.route_id
            depot_id = route.vehicle.depot_location_id
            # Depot start
            writer.writerow([rid, vid, 1, depot_id, "", _fmt_time(0), _fmt_time(0)])
            # Delivery stops
            for i, stop in enumerate(route.stops):
                writer.writerow([
                    rid, vid, i + 2,
                    stop.package.destination_id,
                    stop.package.package_id,
                    _fmt_time(stop.arrival),
                    _fmt_time(stop.departure),
                ])
            # Depot end
            end_pos = len(route.stops) + 2
            writer.writerow([rid, vid, end_pos, depot_id, "",
                             _fmt_time(route.depot_arrival), _fmt_time(route.depot_arrival)])


def write_undeliverable(path: str, entries: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["package_id", "reason"])
        for e in entries:
            writer.writerow([e.package_id, e.reason])


def write_summary(path: str, routes: list, distance_km: dict) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["vehicle_id", "total_distance_km", "total_time_min", "packages_delivered"])
        for route in routes:
            if not route.stops:
                continue
            total_dist = _route_distance(route, distance_km)
            total_time = route.depot_arrival  # minutes from departure (08:00) to return
            delivered = len(route.stops)
            writer.writerow([
                route.vehicle.vehicle_id,
                f"{total_dist:.2f}",
                total_time,
                delivered,
            ])


def _route_distance(route, distance_km: dict) -> float:
    depot = route.vehicle.depot_location_id
    if not route.stops:
        return 0.0
    stops = route.stops
    dist = distance_km.get((depot, stops[0].package.destination_id), 0.0)
    for i in range(len(stops) - 1):
        dist += distance_km.get((stops[i].package.destination_id,
                                 stops[i + 1].package.destination_id), 0.0)
    dist += distance_km.get((stops[-1].package.destination_id, depot), 0.0)
    return dist
