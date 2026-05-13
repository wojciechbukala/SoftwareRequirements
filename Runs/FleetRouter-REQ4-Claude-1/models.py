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
    tw_open: int   # minutes since 8:00 AM
    tw_close: int  # minutes since 8:00 AM
    service_min: int
    priority: int  # 0 or 1


@dataclass
class Vehicle:
    vehicle_id: str
    max_weight_kg: float
    max_volume_m3: float
    depot_location_id: str


class DistanceMatrix:
    def __init__(self):
        self._km: dict[tuple[str, str], float] = {}
        self._min: dict[tuple[str, str], int] = {}

    def add(self, from_id: str, to_id: str, distance_km: float, travel_min: int):
        self._km[(from_id, to_id)] = distance_km
        self._min[(from_id, to_id)] = travel_min

    def get_km(self, from_id: str, to_id: str) -> Optional[float]:
        return self._km.get((from_id, to_id))

    def get_min(self, from_id: str, to_id: str) -> Optional[int]:
        return self._min.get((from_id, to_id))

    def has_path(self, from_id: str, to_id: str) -> bool:
        return (from_id, to_id) in self._min
