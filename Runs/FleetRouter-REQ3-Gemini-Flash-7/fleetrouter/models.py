from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional

TIME_FORMAT = "%H:%M"
DEPOT_DEPARTURE_TIME = datetime.strptime("08:00", TIME_FORMAT).time()
MAX_DRIVER_WORKING_TIME = timedelta(hours=8)

@dataclass
class Location:
    id: str
    name: str

@dataclass
class Distance:
    from_location_id: str
    to_location_id: str
    distance_km: float
    travel_time_min: int

@dataclass
class Package:
    id: str
    destination_id: str
    weight_kg: float
    volume_m3: float
    tw_open: datetime.time
    tw_close: datetime.time
    service_min: int
    priority: int # 0 for non-priority, 1 for priority

@dataclass
class Vehicle:
    id: str
    max_weight_kg: float
    max_volume_m3: float
    depot_location_id: str

@dataclass
class Stop:
    route_id: str
    vehicle_id: str
    stop_position_in_order: int
    location_id: str
    delivery_package_id: str
    arrival_time: datetime.time
    departure_time: datetime.time

@dataclass
class Route:
    vehicle_id: str
    stops: List[Stop] = field(default_factory=list)
    total_distance_km: float = 0.0
    total_time_min: int = 0
    packages_delivered: int = 0

    def add_stop(self, stop: Stop):
        self.stops.append(stop)
        # Recalculate totals - this will be handled by the routing logic,
        # but kept here for conceptual completeness.
