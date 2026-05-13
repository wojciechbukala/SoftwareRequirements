from dataclasses import dataclass
from typing import Dict, Tuple

START_MINUTES = 480       # 08:00 departure time in minutes from midnight
MAX_DRIVER_MINUTES = 480  # 8-hour driver day limit

DistanceMap = Dict[Tuple[str, str], Tuple[float, int]]  # (distance_km, travel_time_min)


def parse_time(time_str: str) -> int:
    """Parse HH:MM string to minutes from midnight."""
    h, m = time_str.strip().split(":")
    return int(h) * 60 + int(m)


def format_time(minutes: int) -> str:
    """Format minutes from midnight to HH:MM string."""
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


@dataclass
class Package:
    package_id: str
    destination_id: str
    weight_kg: float
    volume_m3: float
    tw_open: int   # minutes from midnight
    tw_close: int  # minutes from midnight
    service_min: int
    priority: int  # 0 or 1


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
class StopResult:
    package: Package
    arrival_time: int    # minutes from midnight
    waiting_time: int    # minutes
    departure_time: int  # minutes from midnight
