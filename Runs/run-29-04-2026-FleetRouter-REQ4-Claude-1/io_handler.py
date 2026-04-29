import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from models import Location, Package, Vehicle, Route, DeliveryStop, DepotStop

DEPARTURE_HOUR = 8  # 08:00 start
BASE_MINUTES = DEPARTURE_HOUR * 60


def _parse_time(s: str) -> Optional[int]:
    """Convert HH:MM absolute time to minutes since 08:00."""
    try:
        parts = s.strip().split(":")
        h, m = int(parts[0]), int(parts[1])
        return h * 60 + m - BASE_MINUTES
    except Exception:
        return None


def _format_time(minutes: int) -> str:
    """Convert minutes since 08:00 to HH:MM absolute time."""
    total = BASE_MINUTES + minutes
    h, m = divmod(total, 60)
    return f"{h:02d}:{m:02d}"


def read_locations(path: Path) -> Dict[str, Location]:
    locations = {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                loc_id = row["location_id"].strip()
                name = row["name"].strip()
                locations[loc_id] = Location(id=loc_id, name=name)
    except FileNotFoundError:
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    return locations


def read_vehicles(path: Path, locations: Dict[str, Location]) -> List[Vehicle]:
    vehicles = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                try:
                    v_id = row["vehicle_id"].strip()
                    max_w = float(row["max_weight_kg"])
                    max_v = float(row["max_volume_m3"])
                    depot = row["depot_location_id"].strip()
                    if max_w < 0 or max_v < 0:
                        print(f"vehicles.csv row {i}: negative capacity, skipping", file=sys.stderr)
                        continue
                    if depot not in locations:
                        print(f"vehicles.csv row {i}: unknown depot {depot}, skipping", file=sys.stderr)
                        continue
                    vehicles.append(Vehicle(id=v_id, max_weight_kg=max_w, max_volume_m3=max_v,
                                            depot_location_id=depot))
                except (KeyError, ValueError) as e:
                    print(f"vehicles.csv row {i}: invalid data ({e}), skipping", file=sys.stderr)
    except FileNotFoundError:
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    return vehicles


def read_packages(path: Path, locations: Dict[str, Location]) -> List[Package]:
    packages = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                try:
                    p_id = row["package_id"].strip()
                    dest = row["destination_id"].strip()
                    weight = float(row["weight_kg"])
                    volume = float(row["volume_m3"])
                    tw_open_raw = row["tw_open"].strip()
                    tw_close_raw = row["tw_close"].strip()
                    service = int(row["service_min"])
                    priority_raw = row["priority"].strip()

                    if dest not in locations:
                        print(f"packages.csv row {i}: unknown destination {dest}, skipping", file=sys.stderr)
                        continue
                    if weight < 0 or volume < 0:
                        print(f"packages.csv row {i}: negative weight/volume, skipping", file=sys.stderr)
                        continue
                    if service < 0:
                        print(f"packages.csv row {i}: negative service_min, skipping", file=sys.stderr)
                        continue

                    tw_open = _parse_time(tw_open_raw)
                    tw_close = _parse_time(tw_close_raw)
                    if tw_open is None or tw_close is None:
                        print(f"packages.csv row {i}: invalid time window format, skipping", file=sys.stderr)
                        continue
                    if tw_close <= tw_open:
                        print(f"packages.csv row {i}: tw_close must be > tw_open, skipping", file=sys.stderr)
                        continue

                    if priority_raw not in ("0", "1"):
                        print(f"packages.csv row {i}: invalid priority value '{priority_raw}', skipping", file=sys.stderr)
                        continue
                    priority = int(priority_raw)

                    packages.append(Package(id=p_id, destination_id=dest, weight_kg=weight,
                                            volume_m3=volume, tw_open=tw_open, tw_close=tw_close,
                                            service_min=service, priority=priority))
                except (KeyError, ValueError) as e:
                    print(f"packages.csv row {i}: invalid data ({e}), skipping", file=sys.stderr)
    except FileNotFoundError:
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    return packages


def read_distances(path: Path) -> Dict[Tuple[str, str], Tuple[float, int]]:
    """Returns dict mapping (from_id, to_id) -> (distance_km, travel_time_min)."""
    distances = {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                try:
                    from_id = row["from_location_id"].strip()
                    to_id = row["to_location_id"].strip()
                    dist_km = float(row["distance_km"])
                    travel_min = int(row["travel_time_min"])
                    if dist_km < 0 or travel_min < 0:
                        print(f"distances.csv row {i}: negative values, skipping", file=sys.stderr)
                        continue
                    distances[(from_id, to_id)] = (dist_km, travel_min)
                except (KeyError, ValueError) as e:
                    print(f"distances.csv row {i}: invalid data ({e}), skipping", file=sys.stderr)
    except FileNotFoundError:
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    return distances


def read_inputs(directory: Path):
    locations = read_locations(directory / "locations.csv")
    vehicles = read_vehicles(directory / "vehicles.csv", locations)
    packages = read_packages(directory / "packages.csv", locations)
    distances = read_distances(directory / "distances.csv")
    return locations, vehicles, packages, distances


def write_stops_order(path: Path, routes: List[Route]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["route_id", "vehicle_id", "stop_position_in_order",
                         "location_id", "delivered_id", "arrival_time", "departure_time"])
        for route in routes:
            rid = route.id
            vid = route.vehicle.id
            ds = route.depot_start
            writer.writerow([rid, vid, ds.position, ds.location_id, "",
                             _format_time(ds.arrival), _format_time(ds.departure)])
            for stop in route.delivery_stops:
                writer.writerow([rid, vid, stop.position, stop.location_id, stop.package_id,
                                 _format_time(stop.arrival), _format_time(stop.departure)])
            de = route.depot_end
            writer.writerow([rid, vid, de.position, de.location_id, "",
                             _format_time(de.arrival), _format_time(de.departure)])


def write_undeliverable(path: Path, undeliverable: Dict[str, str]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["package_id", "reason"])
        for pkg_id, reason in sorted(undeliverable.items()):
            writer.writerow([pkg_id, reason])


def write_summary(path: Path, routes: List[Route], distances: Dict[Tuple[str, str], Tuple[float, int]]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["vehicle_id", "total_distance_km", "total_time_min", "packages_delivered"])
        for route in routes:
            dist = round(route.total_distance_km(distances), 2)
            time_min = route.total_time_min()
            pkgs = route.packages_delivered()
            writer.writerow([route.vehicle.id, f"{dist:.2f}", time_min, pkgs])


def write_outputs(directory: Path, routes: List[Route], undeliverable: Dict[str, str],
                  distances: Dict[Tuple[str, str], Tuple[float, int]]):
    write_stops_order(directory / "stops_order.csv", routes)
    write_undeliverable(directory / "undeliverable.csv", undeliverable)
    write_summary(directory / "summary.csv", routes, distances)
