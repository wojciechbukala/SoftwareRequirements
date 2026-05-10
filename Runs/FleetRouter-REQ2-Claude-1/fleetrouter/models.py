from dataclasses import dataclass
from typing import Dict, Tuple

START_TIME_MIN = 480       # Vehicles depart depot at 08:00 (DA-04)
MAX_DRIVER_TIME_MIN = 480  # 8-hour driver limit (FR-03)


def parse_time(s: str) -> int:
    """Convert HH:MM string to minutes from midnight."""
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def format_time(minutes: int) -> str:
    """Convert minutes from midnight to HH:MM string."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@dataclass
class Package:
    package_id: str
    destination_id: str
    weight_kg: float
    volume_m3: float
    tw_open: int   # minutes from midnight
    tw_close: int  # minutes from midnight
    service_min: int
    priority: int


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
class DistanceEntry:
    from_location_id: str
    to_location_id: str
    distance_km: float
    travel_time_min: int


# Mapping (from_id, to_id) -> DistanceEntry
DistanceMap = Dict[Tuple[str, str], DistanceEntry]
