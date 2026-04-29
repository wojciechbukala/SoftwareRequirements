from dataclasses import dataclass, field
from typing import List

DEPOT_DEPARTURE_TIME = 480  # 08:00 in minutes from midnight
MAX_DRIVER_TIME_MIN = 480   # 8 hours


@dataclass
class Package:
    id: str
    destination_id: str
    weight_kg: float
    volume_m3: float
    tw_open: int   # minutes from midnight
    tw_close: int  # minutes from midnight
    service_min: int
    priority: int  # 0 or 1


@dataclass
class Vehicle:
    id: str
    max_weight_kg: float
    max_volume_m3: float
    depot_location_id: str


@dataclass
class Location:
    id: str
    name: str


@dataclass
class DistanceEntry:
    from_id: str
    to_id: str
    distance_km: float
    travel_time_min: int


@dataclass
class Stop:
    position: int
    location_id: str
    package_id: str
    arrival_time: int   # minutes from midnight
    departure_time: int  # minutes from midnight


@dataclass
class Route:
    vehicle_id: str
    depot_id: str
    stops: List[Stop] = field(default_factory=list)
    total_distance_km: float = 0.0
    total_time_min: int = 0
