"""Output file generation for FleetRouter."""

import csv
from pathlib import Path
from typing import Dict, List, Tuple

from .models import Package, RouteResult, Vehicle, minutes_to_time
from .reader import Distances
from .solver import compute_route


def write_stops_order(
    output_dir: Path,
    routes: Dict[str, List[Package]],
    vehicles: List[Vehicle],
    distances: Distances,
) -> None:
    """Write stops_order.csv."""
    vehicle_map = {v.vehicle_id: v for v in vehicles}
    path = output_dir / "stops_order.csv"

    fieldnames = [
        "route_id",
        "vehicle_id",
        "stop_position_in_order",
        "location_id",
        "delivery_package_id",
        "arrival_time",
        "departure_time",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for vehicle in vehicles:
            vid = vehicle.vehicle_id
            pkgs = routes.get(vid, [])
            if not pkgs:
                continue

            result, _ = compute_route(vehicle_map[vid], pkgs, distances)
            if result is None:
                continue

            for i, stop in enumerate(result.stops, start=1):
                writer.writerow(
                    {
                        "route_id": vid,
                        "vehicle_id": vid,
                        "stop_position_in_order": i,
                        "location_id": stop.package.destination_id,
                        "delivery_package_id": stop.package.package_id,
                        "arrival_time": minutes_to_time(stop.arrival_time),
                        "departure_time": minutes_to_time(stop.departure_time),
                    }
                )


def write_summary(
    output_dir: Path,
    routes: Dict[str, List[Package]],
    vehicles: List[Vehicle],
    distances: Distances,
) -> None:
    """Write summary.csv – one row per vehicle, including vehicles with no deliveries."""
    vehicle_map = {v.vehicle_id: v for v in vehicles}
    path = output_dir / "summary.csv"

    fieldnames = ["vehicle_id", "total_distance_km", "total_time_min", "packages_delivered"]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for vehicle in vehicles:
            vid = vehicle.vehicle_id
            pkgs = routes.get(vid, [])

            if pkgs:
                result, _ = compute_route(vehicle_map[vid], pkgs, distances)
                total_dist = round(result.total_distance, 2) if result else 0.0
                total_time = result.total_time if result else 0
                delivered = len(pkgs)
            else:
                total_dist = 0.0
                total_time = 0
                delivered = 0

            writer.writerow(
                {
                    "vehicle_id": vid,
                    "total_distance_km": f"{total_dist:.2f}",
                    "total_time_min": total_time,
                    "packages_delivered": delivered,
                }
            )


def write_undeliverable(
    output_dir: Path,
    undeliverable: List[Tuple[Package, str]],
    pre_undeliverable: List[Tuple[str, str]],
) -> None:
    """Write undeliverable.csv."""
    path = output_dir / "undeliverable.csv"

    fieldnames = ["package_id", "reason"]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Packages excluded at validation stage (invalid time windows)
        for pkg_id, reason in pre_undeliverable:
            writer.writerow({"package_id": pkg_id, "reason": reason})

        # Packages that failed routing assignment
        for pkg, reason in undeliverable:
            writer.writerow({"package_id": pkg.package_id, "reason": reason})


def write_all(
    output_dir: Path,
    routes: Dict[str, List[Package]],
    vehicles: List[Vehicle],
    distances: Distances,
    undeliverable: List[Tuple[Package, str]],
    pre_undeliverable: List[Tuple[str, str]],
) -> None:
    """Write all three output files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_stops_order(output_dir, routes, vehicles, distances)
    write_summary(output_dir, routes, vehicles, distances)
    write_undeliverable(output_dir, undeliverable, pre_undeliverable)
