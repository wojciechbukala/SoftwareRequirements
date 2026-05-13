"""Data models for FleetRouter."""

from dataclasses import dataclass, field
from typing import List, Optional

DEPOT_DEPARTURE_MIN = 8 * 60  # vehicles depart depot at 08:00
MAX_DRIVER_MIN = 8 * 60       # maximum daily driver time: 8 hours


def time_to_minutes(t: str) -> int:
    """Convert HH:MM string to minutes from midnight."""
    h, m = t.strip().split(":")
    return int(h) * 60 + int(m)


def minutes_to_time(m: int) -> str:
    """Convert minutes from midnight to HH:MM string."""
    h = m // 60
    mi = m % 60
    return f"{h:02d}:{mi:02d}"


@dataclass
class Package:
    package_id: str
    destination_id: str
    weight_kg: float
    volume_m3: float
    tw_open: int    # minutes from midnight
    tw_close: int   # minutes from midnight
    service_min: int
    priority: int   # 1 = priority, 0 = normal


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
class StopInfo:
    package: Package
    arrival_time: int    # minutes from midnight
    departure_time: int  # minutes from midnight


@dataclass
class RouteResult:
    stops: List[StopInfo]
    total_distance: float  # km
    total_time: int        # minutes (depot departure to return)
