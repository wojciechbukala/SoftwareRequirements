from dataclasses import dataclass
from typing import List

START_TIME_MIN: int = 480       # 08:00 in minutes from midnight
MAX_DRIVER_TIME_MIN: int = 480  # 8-hour daily driver limit


def minutes_to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def hhmm_to_minutes(s: str) -> int:
    parts = s.strip().split(":")
    return int(parts[0]) * 60 + int(parts[1])


@dataclass
class Package:
    package_id: str
    destination_id: str
    weight_kg: float
    volume_m3: float
    tw_open: int    # minutes from midnight
    tw_close: int   # minutes from midnight
    service_min: int
    priority: int   # 0 or 1


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
class RouteStop:
    stop_position: int
    location_id: str
    package_id: str
    arrival_time: int   # minutes from midnight
    departure_time: int # minutes from midnight


@dataclass
class VehicleRoute:
    vehicle: Vehicle
    package_sequence: List[str]
    stops: List[RouteStop]
    total_distance_km: float
    total_time_min: int
    total_weight_kg: float
    total_volume_m3: float
