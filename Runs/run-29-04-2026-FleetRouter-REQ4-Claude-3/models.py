from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


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
    tw_open: int    # minutes since 08:00
    tw_close: int   # minutes since 08:00
    service_min: int
    priority: int   # 0 or 1


@dataclass
class Vehicle:
    vehicle_id: str
    max_weight_kg: float
    max_volume_m3: float
    depot_location_id: str


@dataclass
class RouteStop:
    position: int
    package_id: str
    location_id: str
    arrival_min: int    # minutes since 08:00
    departure_min: int  # minutes since 08:00


@dataclass
class Route:
    route_id: str
    vehicle: Vehicle
    stops: List[RouteStop]
    depot_arrival_min: int
    total_distance_km: float


@dataclass
class InputData:
    locations: Dict[str, Location]
    packages: Dict[str, Package]
    vehicles: Dict[str, Vehicle]
    distances: Dict[Tuple[str, str], Tuple[float, int]]
    invalid_package_ids: List[str]


@dataclass
class PlanResult:
    routes: List[Route]
    undeliverable: Dict[str, str]  # package_id -> reason_code
