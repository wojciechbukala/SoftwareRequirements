import csv
import os
from typing import Dict, List

from .models import DistanceMap, Package, Vehicle, format_time
from .planner import simulate_route


def write_stops_order(
    path: str,
    vehicles: List[Vehicle],
    assignments: Dict[str, List[Package]],
    dist_map: DistanceMap,
) -> None:
    """Write stops_order.csv with one row per stop per route."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "route_id",
                "vehicle_id",
                "stop_position_in_order",
                "location_id",
                "delivery_package_id",
                "arrival_time",
                "departure_time",
            ]
        )
        for vehicle in vehicles:
            pkgs = assignments.get(vehicle.vehicle_id, [])
            if not pkgs:
                continue
            result, _ = simulate_route(vehicle, pkgs, dist_map)
            if result is None:
                continue
            times, _, _ = result
            route_id = vehicle.vehicle_id
            for position, (pkg, (arrival, departure)) in enumerate(
                zip(pkgs, times), start=1
            ):
                writer.writerow(
                    [
                        route_id,
                        vehicle.vehicle_id,
                        position,
                        pkg.destination_id,
                        pkg.package_id,
                        format_time(arrival),
                        format_time(departure),
                    ]
                )


def write_summary(
    path: str,
    vehicles: List[Vehicle],
    assignments: Dict[str, List[Package]],
    dist_map: DistanceMap,
) -> None:
    """Write summary.csv with one row per vehicle (including vehicles with no deliveries)."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["vehicle_id", "total_distance_km", "total_time_min", "packages_delivered"]
        )
        for vehicle in vehicles:
            pkgs = assignments.get(vehicle.vehicle_id, [])
            if pkgs:
                result, _ = simulate_route(vehicle, pkgs, dist_map)
                if result is not None:
                    _, dist, time = result
                    writer.writerow(
                        [vehicle.vehicle_id, f"{dist:.2f}", int(time), len(pkgs)]
                    )
                    continue
            writer.writerow([vehicle.vehicle_id, "0.00", 0, 0])


def write_undeliverable(path: str, undeliverable: Dict[str, str]) -> None:
    """Write undeliverable.csv with one row per package that could not be assigned."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["package_id", "reason"])
        for pkg_id, reason in sorted(undeliverable.items()):
            writer.writerow([pkg_id, reason])


def ensure_output_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
