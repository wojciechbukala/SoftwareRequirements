from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Location:
    id: str
    name: str


@dataclass
class Package:
    id: str
    destination_id: str
    weight_kg: float
    volume_m3: float
    tw_open: int    # minutes since 08:00
    tw_close: int   # minutes since 08:00
    service_min: int
    priority: int   # 0 or 1


@dataclass
class Vehicle:
    id: str
    max_weight_kg: float
    max_volume_m3: float
    depot_location_id: str


@dataclass
class DeliveryStop:
    position: int
    location_id: str
    package_id: str
    arrival: int    # minutes since 08:00
    departure: int  # minutes since 08:00


@dataclass
class DepotStop:
    position: int
    location_id: str
    arrival: int    # minutes since 08:00
    departure: int  # minutes since 08:00


@dataclass
class Route:
    id: str
    vehicle: Vehicle
    depot_start: DepotStop
    delivery_stops: List[DeliveryStop]
    depot_end: DepotStop

    def total_distance_km(self, distances: dict) -> float:
        if not self.delivery_stops:
            km = distances.get(
                (self.vehicle.depot_location_id, self.vehicle.depot_location_id), (0.0, 0)
            )[0]
            return km
        total = 0.0
        prev = self.vehicle.depot_location_id
        for stop in self.delivery_stops:
            total += distances.get((prev, stop.location_id), (0.0, 0))[0]
            prev = stop.location_id
        total += distances.get((prev, self.vehicle.depot_location_id), (0.0, 0))[0]
        return total

    def total_time_min(self) -> int:
        return self.depot_end.arrival

    def packages_delivered(self) -> int:
        return len(self.delivery_stops)
