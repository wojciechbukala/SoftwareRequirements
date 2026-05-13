from dataclasses import dataclass, field
from typing import Optional, List


DEPOT_DEPARTURE = 8 * 60   # 08:00 in minutes from midnight
MAX_DRIVER_MINUTES = 8 * 60  # 480 minutes


def parse_time(s: str) -> int:
    h, m = s.strip().split(':')
    return int(h) * 60 + int(m)


def format_time(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


@dataclass
class Package:
    id: str
    location_id: str
    weight: float
    volume: float
    time_open: int   # minutes from midnight
    time_close: int  # minutes from midnight
    service_duration: int  # minutes
    priority: bool


@dataclass
class Vehicle:
    id: str
    max_weight: float
    max_volume: float
    depot_id: str


@dataclass
class Location:
    id: str
    name: str


@dataclass
class Stop:
    location_id: str
    package_id: Optional[str]
    arrival_time: int
    departure_time: int


@dataclass
class Route:
    vehicle: Vehicle
    package_ids: List[str] = field(default_factory=list)
    stops: List[Stop] = field(default_factory=list)
    total_distance: float = 0.0
    total_duration: int = 0
    weight_used: float = 0.0
    volume_used: float = 0.0
