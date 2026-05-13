from typing import List, Optional

from .models import (
    DistanceMap,
    MAX_DRIVER_MINUTES,
    START_MINUTES,
    Package,
    StopResult,
    Vehicle,
)


class Route:
    def __init__(self, vehicle: Vehicle, stops: Optional[List[Package]] = None) -> None:
        self.vehicle = vehicle
        self.stops: List[Package] = stops if stops is not None else []

    def copy(self) -> "Route":
        return Route(self.vehicle, list(self.stops))

    def compute_schedule(self, distances: DistanceMap) -> Optional[List[StopResult]]:
        """Compute arrival/departure times for every stop.

        Returns None if any required distance entry is missing or a time window
        cannot be met (vehicle arrives after tw_close).
        """
        schedule: List[StopResult] = []
        current_time = START_MINUTES
        current_loc = self.vehicle.depot_location_id

        for pkg in self.stops:
            key = (current_loc, pkg.destination_id)
            if key not in distances:
                return None
            _, travel_min = distances[key]
            arrival = current_time + travel_min
            if arrival > pkg.tw_close:
                return None
            wait = max(0, pkg.tw_open - arrival)
            departure = arrival + wait + pkg.service_min
            schedule.append(StopResult(pkg, arrival, wait, departure))
            current_time = departure
            current_loc = pkg.destination_id

        if self.stops:
            return_key = (self.stops[-1].destination_id, self.vehicle.depot_location_id)
            if return_key not in distances:
                return None

        return schedule

    def total_distance(self, distances: DistanceMap) -> float:
        if not self.stops:
            return 0.0
        dist = 0.0
        loc = self.vehicle.depot_location_id
        for pkg in self.stops:
            d, _ = distances.get((loc, pkg.destination_id), (float("inf"), 0))
            dist += d
            loc = pkg.destination_id
        d, _ = distances.get((loc, self.vehicle.depot_location_id), (float("inf"), 0))
        dist += d
        return dist

    def total_duration(self, distances: DistanceMap) -> int:
        """Total elapsed minutes from depot departure to depot return."""
        if not self.stops:
            return 0
        schedule = self.compute_schedule(distances)
        if schedule is None:
            return MAX_DRIVER_MINUTES + 1
        last_dep = schedule[-1].departure_time
        last_loc = self.stops[-1].destination_id
        _, return_travel = distances.get(
            (last_loc, self.vehicle.depot_location_id), (0, 0)
        )
        return last_dep + return_travel - START_MINUTES

    def total_weight(self) -> float:
        return sum(p.weight_kg for p in self.stops)

    def total_volume(self) -> float:
        return sum(p.volume_m3 for p in self.stops)

    def is_weight_ok(self) -> bool:
        return self.total_weight() <= self.vehicle.max_weight_kg

    def is_volume_ok(self) -> bool:
        return self.total_volume() <= self.vehicle.max_volume_m3

    def is_feasible(self, distances: DistanceMap) -> bool:
        if not self.is_weight_ok() or not self.is_volume_ok():
            return False
        schedule = self.compute_schedule(distances)
        if schedule is None:
            return False
        if not self.stops:
            return True
        last_dep = schedule[-1].departure_time
        last_loc = self.stops[-1].destination_id
        _, return_travel = distances.get(
            (last_loc, self.vehicle.depot_location_id), (0, 0)
        )
        duration = last_dep + return_travel - START_MINUTES
        return duration <= MAX_DRIVER_MINUTES
