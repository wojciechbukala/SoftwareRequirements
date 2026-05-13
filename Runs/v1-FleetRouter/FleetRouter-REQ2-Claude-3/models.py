from dataclasses import dataclass, field
from typing import List

START_TIME_MIN = 8 * 60  # 08:00 in minutes from midnight
MAX_DRIVER_TIME_MIN = 8 * 60  # 480 minutes (8 hours)


@dataclass
class Package:
    package_id: str
    destination_id: str
    weight_kg: float
    volume_m3: float
    tw_open: int   # minutes from midnight
    tw_close: int  # minutes from midnight
    service_min: int
    priority: int  # 1 = priority, 0 = normal


@dataclass
class Vehicle:
    vehicle_id: str
    max_weight_kg: float
    max_volume_m3: float
    depot_location_id: str


@dataclass
class Location:
    location_id: str
    name: str


@dataclass
class Stop:
    package: Package
    arrival_time: int    # minutes from midnight
    waiting_time: int    # minutes
    departure_time: int  # minutes from midnight


@dataclass
class Route:
    route_id: int
    vehicle: Vehicle
    stops: List[Stop] = field(default_factory=list)
    total_distance_km: float = 0.0
    total_duration_min: int = 0
