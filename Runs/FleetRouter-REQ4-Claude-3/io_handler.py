import csv
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from models import InputData, Location, Package, PlanResult, Route, Vehicle


def hhmm_to_minutes(time_str: str) -> int:
    """Convert HH:MM to minutes since 08:00."""
    parts = time_str.strip().split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    return (hours - 8) * 60 + minutes


def minutes_to_hhmm(minutes: int) -> str:
    """Convert minutes since 08:00 to HH:MM."""
    total = 8 * 60 + minutes
    return f"{total // 60:02d}:{total % 60:02d}"


def read_inputs(input_dir: Path) -> InputData:
    locations = _read_locations(input_dir / "locations.csv")
    vehicles = _read_vehicles(input_dir / "vehicles.csv", locations)
    packages, invalid_ids = _read_packages(input_dir / "packages.csv", locations)
    distances = _read_distances(input_dir / "distances.csv")
    return InputData(
        locations=locations,
        packages=packages,
        vehicles=vehicles,
        distances=distances,
        invalid_package_ids=invalid_ids,
    )


def _read_locations(path: Path) -> Dict[str, Location]:
    locations = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            loc = Location(location_id=row["location_id"], name=row["name"])
            locations[loc.location_id] = loc
    return locations


def _read_vehicles(path: Path, locations: Dict[str, Location]) -> Dict[str, Vehicle]:
    vehicles = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                v = Vehicle(
                    vehicle_id=row["vehicle_id"],
                    max_weight_kg=float(row["max_weight_kg"]),
                    max_volume_m3=float(row["max_volume_m3"]),
                    depot_location_id=row["depot_location_id"],
                )
                if v.max_weight_kg < 0 or v.max_volume_m3 < 0:
                    continue
                if v.depot_location_id not in locations:
                    continue
                vehicles[v.vehicle_id] = v
            except (ValueError, KeyError):
                pass
    return vehicles


def _read_packages(
    path: Path, locations: Dict[str, Location]
) -> Tuple[Dict[str, Package], List[str]]:
    packages = {}
    invalid_ids = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pkg_id = row.get("package_id", "")
            try:
                priority = int(row["priority"])
                if priority not in (0, 1):
                    invalid_ids.append(pkg_id)
                    continue
                pkg = Package(
                    package_id=pkg_id,
                    destination_id=row["destination_id"],
                    weight_kg=float(row["weight_kg"]),
                    volume_m3=float(row["volume_m3"]),
                    tw_open=hhmm_to_minutes(row["tw_open"]),
                    tw_close=hhmm_to_minutes(row["tw_close"]),
                    service_min=int(row["service_min"]),
                    priority=priority,
                )
                if (
                    pkg.weight_kg < 0
                    or pkg.volume_m3 < 0
                    or pkg.tw_open < 0
                    or pkg.tw_close <= pkg.tw_open
                    or pkg.service_min < 0
                    or pkg.destination_id not in locations
                ):
                    invalid_ids.append(pkg_id)
                    continue
                packages[pkg.package_id] = pkg
            except (ValueError, KeyError):
                if pkg_id:
                    invalid_ids.append(pkg_id)
    return packages, invalid_ids


def _read_distances(
    path: Path,
) -> Dict[Tuple[str, str], Tuple[float, int]]:
    distances = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                from_id = row["from_location_id"]
                to_id = row["to_location_id"]
                dist_km = float(row["distance_km"])
                travel_min = int(row["travel_time_min"])
                if dist_km >= 0 and travel_min >= 0:
                    distances[(from_id, to_id)] = (dist_km, travel_min)
            except (ValueError, KeyError):
                pass
    return distances


def write_outputs(plan: PlanResult, data: InputData, output_dir: Path) -> None:
    _write_stops_order(plan.routes, output_dir / "stops_order.csv")
    _write_undeliverable(plan.undeliverable, output_dir / "undeliverable.csv")
    _write_summary(plan.routes, data.vehicles, output_dir / "summary.csv")


def _write_stops_order(routes: List[Route], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "route_id",
                "vehicle_id",
                "stop_position_in_order",
                "location_id",
                "delivered_id",
                "arrival_time",
                "departure_time",
            ]
        )
        for route in routes:
            v = route.vehicle
            depot_id = v.depot_location_id
            # Depot start
            writer.writerow(
                [route.route_id, v.vehicle_id, 1, depot_id, "", "08:00", "08:00"]
            )
            # Delivery stops
            for stop in route.stops:
                writer.writerow(
                    [
                        route.route_id,
                        v.vehicle_id,
                        stop.position + 1,
                        stop.location_id,
                        stop.package_id,
                        minutes_to_hhmm(stop.arrival_min),
                        minutes_to_hhmm(stop.departure_min),
                    ]
                )
            # Depot end
            end_pos = len(route.stops) + 2
            writer.writerow(
                [
                    route.route_id,
                    v.vehicle_id,
                    end_pos,
                    depot_id,
                    "",
                    minutes_to_hhmm(route.depot_arrival_min),
                    minutes_to_hhmm(route.depot_arrival_min),
                ]
            )


def _write_undeliverable(undeliverable: Dict[str, str], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["package_id", "reason"])
        for pkg_id, reason in sorted(undeliverable.items()):
            writer.writerow([pkg_id, reason])


def _write_summary(
    routes: List[Route], vehicles: Dict[str, Vehicle], path: Path
) -> None:
    delivered_counts = {r.vehicle.vehicle_id: len(r.stops) for r in routes}
    distances = {r.vehicle.vehicle_id: r.total_distance_km for r in routes}
    durations = {r.vehicle.vehicle_id: r.depot_arrival_min for r in routes}

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["vehicle_id", "total_distance_km", "total_time_min", "packages_delivered"]
        )
        for v_id in vehicles:
            dist = distances.get(v_id, 0.0)
            duration = durations.get(v_id, 0)
            count = delivered_counts.get(v_id, 0)
            writer.writerow([v_id, f"{dist:.2f}", duration, count])
