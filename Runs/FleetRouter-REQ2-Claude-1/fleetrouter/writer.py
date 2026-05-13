import csv
from pathlib import Path
from typing import List, Tuple

from .models import Vehicle, VehicleRoute, minutes_to_hhmm


def write_stops_order(path: Path, routes: List[VehicleRoute]) -> None:
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
        for route in sorted(routes, key=lambda r: r.vehicle.vehicle_id):
            for stop in route.stops:
                writer.writerow(
                    [
                        route.vehicle.vehicle_id,  # route_id = vehicle_id (one route per vehicle)
                        route.vehicle.vehicle_id,
                        stop.stop_position,
                        stop.location_id,
                        stop.package_id,
                        minutes_to_hhmm(stop.arrival_time),
                        minutes_to_hhmm(stop.departure_time),
                    ]
                )


def write_summary(
    path: Path, routes: List[VehicleRoute], vehicles: List[Vehicle]
) -> None:
    route_by_vehicle = {r.vehicle.vehicle_id: r for r in routes}

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["vehicle_id", "total_distance_km", "total_time_min", "packages_delivered"]
        )
        for vehicle in vehicles:
            route = route_by_vehicle.get(vehicle.vehicle_id)
            if route and route.package_sequence:
                writer.writerow(
                    [
                        vehicle.vehicle_id,
                        f"{route.total_distance_km:.2f}",
                        route.total_time_min,
                        len(route.package_sequence),
                    ]
                )
            else:
                writer.writerow([vehicle.vehicle_id, "0.00", 0, 0])


def write_undeliverable(
    path: Path, undeliverable: List[Tuple[str, str]]
) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["package_id", "reason"])
        for pkg_id, reason in undeliverable:
            writer.writerow([pkg_id, reason])
