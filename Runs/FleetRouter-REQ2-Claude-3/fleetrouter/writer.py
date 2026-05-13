import csv
import os
from typing import Dict, List, Tuple

from .models import DistanceMap, Vehicle, format_time
from .route import Route


def write_stops_order(
    routes: Dict[str, Route], distances: DistanceMap, output_dir: str
) -> None:
    path = os.path.join(output_dir, "stops_order.csv")
    fieldnames = [
        "route_id",
        "vehicle_id",
        "stop_position_in_order",
        "location_id",
        "delivery_package_id",
        "arrival_time",
        "departure_time",
    ]

    rows = []
    for vid, route in sorted(routes.items()):
        if not route.stops:
            continue
        schedule = route.compute_schedule(distances)
        if schedule is None:
            continue
        for position, stop_result in enumerate(schedule, start=1):
            rows.append(
                {
                    "route_id": vid,
                    "vehicle_id": vid,
                    "stop_position_in_order": position,
                    "location_id": stop_result.package.destination_id,
                    "delivery_package_id": stop_result.package.package_id,
                    "arrival_time": format_time(stop_result.arrival_time),
                    "departure_time": format_time(stop_result.departure_time),
                }
            )

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(
    routes: Dict[str, Route],
    all_vehicles: List[Vehicle],
    distances: DistanceMap,
    output_dir: str,
) -> None:
    path = os.path.join(output_dir, "summary.csv")
    fieldnames = [
        "vehicle_id",
        "total_distance_km",
        "total_time_min",
        "packages_delivered",
    ]

    rows = []
    for vehicle in all_vehicles:
        route = routes.get(vehicle.vehicle_id)
        if route and route.stops:
            dist = route.total_distance(distances)
            duration = route.total_duration(distances)
            count = len(route.stops)
        else:
            dist = 0.0
            duration = 0
            count = 0

        rows.append(
            {
                "vehicle_id": vehicle.vehicle_id,
                "total_distance_km": round(dist, 2),
                "total_time_min": duration,
                "packages_delivered": count,
            }
        )

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_undeliverable(
    undeliverable: Dict[str, str], output_dir: str
) -> None:
    path = os.path.join(output_dir, "undeliverable.csv")
    fieldnames = ["package_id", "reason"]

    rows = [
        {"package_id": pid, "reason": reason}
        for pid, reason in sorted(undeliverable.items())
    ]

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
