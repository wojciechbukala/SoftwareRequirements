import csv
import os
from typing import List, Tuple
from models import Route


def _minutes_to_hhmm(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def write_stops_order(routes: List[Route], output_dir: str) -> None:
    filepath = os.path.join(output_dir, "stops_order.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
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
        for route in sorted(routes, key=lambda r: r.vehicle.vehicle_id):
            for position, stop in enumerate(route.stops, start=1):
                writer.writerow(
                    [
                        route.route_id,
                        route.vehicle.vehicle_id,
                        position,
                        stop.package.destination_id,
                        stop.package.package_id,
                        _minutes_to_hhmm(stop.arrival_time),
                        _minutes_to_hhmm(stop.departure_time),
                    ]
                )


def write_summary(routes: List[Route], output_dir: str) -> None:
    filepath = os.path.join(output_dir, "summary.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["vehicle_id", "total_distance_km", "total_time_min", "packages_delivered"]
        )
        for route in sorted(routes, key=lambda r: r.vehicle.vehicle_id):
            writer.writerow(
                [
                    route.vehicle.vehicle_id,
                    f"{route.total_distance_km:.2f}",
                    route.total_duration_min,
                    len(route.stops),
                ]
            )


def write_undeliverable(
    undeliverable: List[Tuple[str, str]], output_dir: str
) -> None:
    filepath = os.path.join(output_dir, "undeliverable.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["package_id", "reason"])
        for pkg_id, reason in undeliverable:
            writer.writerow([pkg_id, reason])
