from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Location:
    location_id: str
    name: str


@dataclass
class Package:
    package_id: str
    destination_id: str
    weight_kg: float
    volume_m3: float
    tw_open: int   # minutes since 08:00
    tw_close: int  # minutes since 08:00
    service_min: int
    priority: int  # 0 or 1


@dataclass
class Vehicle:
    vehicle_id: str
    max_weight_kg: float
    max_volume_m3: float
    depot_location_id: str


@dataclass
class DeliveryStop:
    package: Package
    position: int
    arrival: int    # minutes since 08:00
    departure: int  # minutes since 08:00


@dataclass
class Route:
    route_id: int
    vehicle: Vehicle
    stops: list = field(default_factory=list)  # list of DeliveryStop, ordered by position
    depot_arrival: int = 0   # arrival back at depot (minutes since 08:00)

    def total_weight(self) -> float:
        return sum(s.package.weight_kg for s in self.stops)

    def total_volume(self) -> float:
        return sum(s.package.volume_m3 for s in self.stops)


@dataclass
class UndeliverableEntry:
    package_id: str
    reason: str  # CAPACITY_WEIGHT | CAPACITY_VOLUME | TIME_WINDOW | MAX_DRIVER_TIME | NO_VEHICLE | UNREACHABLE
