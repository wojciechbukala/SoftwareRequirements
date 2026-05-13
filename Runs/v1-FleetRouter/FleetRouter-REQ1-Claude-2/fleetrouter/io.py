"""CSV input/output for FleetRouter."""
import csv
import os
from typing import Dict, List, Tuple

from .models import Package, Vehicle, Location, parse_time


def _get(row: dict, *keys: str, default=None):
    """Get first matching key from dict, case-insensitive."""
    row_lower = {k.lower().strip(): v for k, v in row.items()}
    for k in keys:
        v = row_lower.get(k.lower())
        if v is not None:
            return v.strip() if isinstance(v, str) else v
    return default


def read_locations(path: str) -> Dict[str, Location]:
    locations = {}
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            lid = _get(row, 'location_id', 'id', 'loc_id')
            name = _get(row, 'name', 'location_name')
            locations[lid] = Location(id=lid, name=name)
    return locations


def read_vehicles(path: str) -> List[Vehicle]:
    vehicles = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            v = Vehicle(
                id=_get(row, 'vehicle_id', 'id'),
                max_weight=float(_get(row, 'max_weight', 'capacity_weight', 'weight_capacity', 'max_weight_kg')),
                max_volume=float(_get(row, 'max_volume', 'capacity_volume', 'volume_capacity', 'max_volume_m3')),
                depot_id=_get(row, 'depot_id', 'depot', 'depot_location', 'depot_location_id'),
            )
            vehicles.append(v)
    return vehicles


def read_packages(path: str) -> List[Package]:
    packages = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            priority_val = _get(row, 'priority', 'is_priority', 'urgent').lower()
            p = Package(
                id=_get(row, 'package_id', 'id'),
                location_id=_get(row, 'location_id', 'destination', 'delivery_location', 'loc_id', 'destination_id'),
                weight=float(_get(row, 'weight', 'weight_kg')),
                volume=float(_get(row, 'volume', 'volume_m3')),
                time_open=parse_time(_get(row, 'time_open', 'open', 'opening_time', 'window_open', 'tw_open', 'start')),
                time_close=parse_time(_get(row, 'time_close', 'close', 'closing_time', 'window_close', 'tw_close', 'end')),
                service_duration=int(_get(row, 'service_duration', 'service_time', 'duration', 'service')),
                priority=priority_val in ('true', '1', 'yes'),
            )
            packages.append(p)
    return packages


def read_distances(path: str) -> Dict[Tuple[str, str], Tuple[float, int]]:
    """Returns {(from_id, to_id): (distance_km, travel_minutes)}."""
    distances = {}
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            from_id = _get(row, 'from_id', 'from', 'origin', 'from_location', 'from_location_id', 'source')
            to_id = _get(row, 'to_id', 'to', 'destination', 'to_location', 'to_location_id', 'target')
            dist = float(_get(row, 'distance', 'dist', 'distance_km', 'km'))
            time = int(_get(row, 'travel_time', 'time', 'duration', 'travel_time_min', 'minutes', 'travel_minutes'))
            distances[(from_id, to_id)] = (dist, time)
    return distances


def write_stops_order(path: str, routes):
    from .models import format_time
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['route_id', 'vehicle_id', 'stop_order', 'location_id',
                         'package_id', 'arrival_time', 'departure_time'])
        for route_idx, route in enumerate(routes, start=1):
            route_id = f"ROUTE_{route_idx}"
            for order, stop in enumerate(route.stops, start=1):
                writer.writerow([
                    route_id,
                    route.vehicle.id,
                    order,
                    stop.location_id,
                    stop.package_id if stop.package_id else '',
                    format_time(stop.arrival_time),
                    format_time(stop.departure_time),
                ])


def write_undeliverable(path: str, undeliverable: List[Tuple[str, str]]):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['package_id', 'reason'])
        for pkg_id, reason in undeliverable:
            writer.writerow([pkg_id, reason])


def write_summary(path: str, routes):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['vehicle_id', 'total_distance', 'total_duration', 'packages_delivered'])
        for route in routes:
            writer.writerow([
                route.vehicle.id,
                f"{route.total_distance:.2f}",
                route.total_duration,
                len(route.package_ids),
            ])
