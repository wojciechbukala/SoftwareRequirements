import csv
from typing import List, Tuple

from .models import Route


def minutes_to_hhmm(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def write_stops_order(routes: List[Route], filepath: str) -> None:
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
        for route in sorted(routes, key=lambda r: r.vehicle_id):
            for stop in route.stops:
                writer.writerow(
                    [
                        route.vehicle_id,
                        route.vehicle_id,
                        stop.position,
                        stop.location_id,
                        stop.package_id,
                        minutes_to_hhmm(stop.arrival_time),
                        minutes_to_hhmm(stop.departure_time),
                    ]
                )


def write_summary(routes: List[Route], filepath: str) -> None:
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["vehicle_id", "total_distance_km", "total_time_min", "packages_delivered"]
        )
        for route in sorted(routes, key=lambda r: r.vehicle_id):
            writer.writerow(
                [
                    route.vehicle_id,
                    f"{route.total_distance_km:.2f}",
                    route.total_time_min,
                    len(route.stops),
                ]
            )


def write_undeliverable(
    undeliverable: List[Tuple[str, str]], filepath: str
) -> None:
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["package_id", "reason"])
        for pkg_id, reason in sorted(undeliverable, key=lambda x: x[0]):
            writer.writerow([pkg_id, reason])
