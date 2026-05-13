#!/usr/bin/env python3
"""FleetRouter - daily route planner for a courier company."""

import argparse
import csv
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

DEPARTURE_MIN = 8 * 60   # 480 minutes = 08:00
MAX_WORK_MIN  = 8 * 60   # 480 minutes driver limit
EPS = 1e-9


def parse_time(s: str) -> int:
    """HH:MM -> minutes since midnight."""
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def fmt_time(minutes: int) -> str:
    """Minutes since midnight -> HH:MM."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@dataclass
class Package:
    package_id: str
    destination_id: str
    weight_kg: float
    volume_m3: float
    tw_open: int
    tw_close: int
    service_min: int
    priority: int


@dataclass
class Vehicle:
    vehicle_id: str
    max_weight_kg: float
    max_volume_m3: float
    depot_location_id: str


Distances = Dict[Tuple[str, str], Tuple[float, int]]  # (dist_km, travel_min)


class VehicleRoute:
    def __init__(self, vehicle: Vehicle):
        self.vehicle = vehicle
        self.packages: List[Package] = []
        self.used_weight: float = 0.0
        self.used_volume: float = 0.0

    def _locs(self) -> List[str]:
        depot = self.vehicle.depot_location_id
        return [depot] + [p.destination_id for p in self.packages] + [depot]

    def _timing(self, distances: Distances) -> Tuple[Optional[List[Tuple[int, int]]], Optional[str]]:
        """
        Compute (arrival, departure) for each position in the route.
        Returns (times_list, None) on success, or (None, reason) on failure.
        reason is one of: UNREACHABLE, TIME_WINDOW, MAX_DRIVER_TIME.
        """
        locs = self._locs()
        times: List[Tuple[int, int]] = []
        current = DEPARTURE_MIN
        times.append((current, current))  # depot departure

        for i in range(1, len(locs)):
            key = (locs[i - 1], locs[i])
            if key not in distances:
                return None, "UNREACHABLE"
            travel_min = distances[key][1]
            arrival = times[-1][1] + travel_min

            if i < len(locs) - 1:  # delivery stop
                pkg = self.packages[i - 1]
                wait_until = max(arrival, pkg.tw_open)
                if wait_until > pkg.tw_close:
                    return None, "TIME_WINDOW"
                departure = wait_until + pkg.service_min
            else:  # return to depot
                departure = arrival

            times.append((arrival, departure))

        total_time = times[-1][0] - times[0][1]
        if total_time > MAX_WORK_MIN:
            return None, "MAX_DRIVER_TIME"

        return times, None

    def _distance(self, distances: Distances) -> float:
        locs = self._locs()
        total = 0.0
        for i in range(len(locs) - 1):
            key = (locs[i], locs[i + 1])
            if key not in distances:
                return float("inf")
            total += distances[key][0]
        return total

    def try_best_insert(self, pkg: Package, distances: Distances
                        ) -> Tuple[bool, Optional[str], int, float, int]:
        """
        Find the cheapest feasible insertion position for pkg.
        Returns (feasible, reason_if_not, best_pos, added_dist_km, total_route_min).
        """
        # Capacity pre-checks
        if self.used_weight + pkg.weight_kg > self.vehicle.max_weight_kg + EPS:
            return False, "CAPACITY_WEIGHT", -1, 0.0, 0
        if self.used_volume + pkg.volume_m3 > self.vehicle.max_volume_m3 + EPS:
            return False, "CAPACITY_VOLUME", -1, 0.0, 0

        old_dist = self._distance(distances)
        best_pos = -1
        best_added = float("inf")
        best_dur = float("inf")
        worst_reason = "NO_VEHICLE"

        REASON_PRIORITY = {"UNREACHABLE": 1, "TIME_WINDOW": 2,
                           "MAX_DRIVER_TIME": 3, "NO_VEHICLE": 4}

        for pos in range(len(self.packages) + 1):
            self.packages.insert(pos, pkg)
            times, reason = self._timing(distances)
            if times is not None:
                new_dist = self._distance(distances)
                added = new_dist - old_dist
                dur = times[-1][0] - times[0][1]
                if added < best_added - EPS or (abs(added - best_added) < EPS and dur < best_dur):
                    best_added = added
                    best_dur = dur
                    best_pos = pos
            else:
                if reason and REASON_PRIORITY.get(reason, 99) < REASON_PRIORITY.get(worst_reason, 99):
                    worst_reason = reason
            self.packages.pop(pos)

        if best_pos >= 0:
            return True, None, best_pos, best_added, int(best_dur)
        return False, worst_reason, -1, 0.0, 0

    def insert_at(self, pkg: Package, pos: int):
        self.packages.insert(pos, pkg)
        self.used_weight += pkg.weight_kg
        self.used_volume += pkg.volume_m3

    def get_timing(self, distances: Distances) -> Optional[List[Tuple[int, int]]]:
        times, _ = self._timing(distances)
        return times

    def get_distance(self, distances: Distances) -> float:
        return self._distance(distances)

    def get_duration(self, distances: Distances) -> int:
        times, _ = self._timing(distances)
        if times is None:
            return 0
        return times[-1][0] - times[0][1]


def load_csv(path: str) -> List[Dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def save_csv(path: str, fieldnames: List[str], rows: List[Dict]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _vol_key(row: Dict) -> str:
    """Find the volume column name (handles UTF-8 variants of m³)."""
    for k in row:
        if k.startswith("volume"):
            return k
    raise KeyError(f"No volume column found in {list(row.keys())}")


def _failure_reason(pkg: Package, routes: List[VehicleRoute],
                    distances: Distances) -> str:
    """Determine why a package could not be assigned."""
    # Check weight: any vehicle with sufficient remaining weight?
    any_weight = any(
        r.vehicle.max_weight_kg - r.used_weight >= pkg.weight_kg - EPS
        for r in routes
    )
    if not any_weight:
        return "CAPACITY_WEIGHT"

    # Check volume
    any_volume = any(
        r.vehicle.max_volume_m3 - r.used_volume >= pkg.volume_m3 - EPS
        for r in routes
    )
    if not any_volume:
        return "CAPACITY_VOLUME"

    # Routing failures among capacity-capable vehicles
    routing_failures: Set[str] = set()
    for r in routes:
        if (r.vehicle.max_weight_kg - r.used_weight < pkg.weight_kg - EPS or
                r.vehicle.max_volume_m3 - r.used_volume < pkg.volume_m3 - EPS):
            continue
        for pos in range(len(r.packages) + 1):
            r.packages.insert(pos, pkg)
            _, reason = r._timing(distances)
            r.packages.pop(pos)
            if reason:
                routing_failures.add(reason)

    for code in ("TIME_WINDOW", "MAX_DRIVER_TIME", "UNREACHABLE"):
        if code in routing_failures:
            return code

    return "NO_VEHICLE"


def main():
    parser = argparse.ArgumentParser(description="FleetRouter - courier route planner")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    in_dir, out_dir = args.input, args.output
    os.makedirs(out_dir, exist_ok=True)

    # Load raw data
    packages_raw  = load_csv(os.path.join(in_dir, "packages.csv"))
    vehicles_raw  = load_csv(os.path.join(in_dir, "vehicles.csv"))
    locations_raw = load_csv(os.path.join(in_dir, "locations.csv"))
    distances_raw = load_csv(os.path.join(in_dir, "distances.csv"))

    # Locations set
    locations: Set[str] = {row["location_id"] for row in locations_raw}

    # Distances dict
    distances: Distances = {}
    for row in distances_raw:
        key = (row["from_location_id"], row["to_location_id"])
        distances[key] = (float(row["distance_km"]), int(row["travel_time_min"]))

    undeliverable: List[Dict] = []

    # Parse vehicles — exclude those with unknown depot (not reported per spec)
    vehicles: List[Vehicle] = []
    for row in vehicles_raw:
        if row["depot_location_id"] not in locations:
            continue
        vehicles.append(Vehicle(
            vehicle_id=row["vehicle_id"],
            max_weight_kg=float(row["max_weight_kg"]),
            max_volume_m3=float(row["max_volume_m3"]),
            depot_location_id=row["depot_location_id"],
        ))

    # Parse packages
    packages_valid: List[Package] = []
    for row in packages_raw:
        pid = row["package_id"]
        dest = row["destination_id"]

        # Unknown destination location
        if dest not in locations:
            undeliverable.append({"package_id": pid, "reason": "UNREACHABLE"})
            continue

        # Parse time window
        try:
            tw_open  = parse_time(row["tw_open"])
            tw_close = parse_time(row["tw_close"])
        except (ValueError, KeyError):
            undeliverable.append({"package_id": pid, "reason": "TIME_WINDOW"})
            continue

        if tw_open >= tw_close:
            undeliverable.append({"package_id": pid, "reason": "TIME_WINDOW"})
            continue

        vol_key = _vol_key(row)
        packages_valid.append(Package(
            package_id=pid,
            destination_id=dest,
            weight_kg=float(row["weight_kg"]),
            volume_m3=float(row[vol_key]),
            tw_open=tw_open,
            tw_close=tw_close,
            service_min=int(row["service_min"]),
            priority=int(row["priority"]),
        ))

    # Priority packages first, then stable by package_id
    packages_valid.sort(key=lambda p: (-p.priority, p.package_id))

    # Pre-filter: UNREACHABLE — no vehicle depot can reach destination and return
    packages_to_assign: List[Package] = []
    for pkg in packages_valid:
        reachable = False
        if vehicles:
            for v in vehicles:
                if ((v.depot_location_id, pkg.destination_id) in distances and
                        (pkg.destination_id, v.depot_location_id) in distances):
                    reachable = True
                    break
        else:
            # No vehicles at all — check if destination exists in distances at all
            reachable = False

        if not reachable:
            undeliverable.append({"package_id": pkg.package_id, "reason": "UNREACHABLE"})
        else:
            packages_to_assign.append(pkg)

    # Build routes for each vehicle
    routes: List[VehicleRoute] = [VehicleRoute(v) for v in vehicles]

    # Assign packages using cheapest-insertion heuristic
    for pkg in packages_to_assign:
        best_route_idx = -1
        best_pos = -1
        best_added = float("inf")
        best_dur = float("inf")

        for i, route in enumerate(routes):
            feasible, _, pos, added, dur = route.try_best_insert(pkg, distances)
            if feasible:
                if added < best_added - EPS or (abs(added - best_added) < EPS and dur < best_dur):
                    best_added = added
                    best_dur = dur
                    best_route_idx = i
                    best_pos = pos

        if best_route_idx >= 0:
            routes[best_route_idx].insert_at(pkg, best_pos)
        else:
            reason = _failure_reason(pkg, routes, distances)
            undeliverable.append({"package_id": pkg.package_id, "reason": reason})

    # Build output rows
    stops_rows: List[Dict] = []
    summary_rows: List[Dict] = []

    for route in routes:
        vid = route.vehicle.vehicle_id
        n_pkgs = len(route.packages)

        if n_pkgs == 0:
            summary_rows.append({
                "vehicle_id": vid,
                "total_distance_km": "0.00",
                "total_time_min": 0,
                "packages_delivered": 0,
            })
            continue

        times = route.get_timing(distances)
        total_dist = route.get_distance(distances)
        total_dur  = route.get_duration(distances)
        route_id   = f"route_{vid}"

        for i, pkg in enumerate(route.packages):
            arr = times[i + 1][0]
            dep = times[i + 1][1]
            stops_rows.append({
                "route_id": route_id,
                "vehicle_id": vid,
                "stop_position_in_order": i + 1,
                "location_id": pkg.destination_id,
                "delivered_id": pkg.package_id,
                "arrival_time": fmt_time(arr),
                "departure_time": fmt_time(dep),
            })

        summary_rows.append({
            "vehicle_id": vid,
            "total_distance_km": f"{total_dist:.2f}",
            "total_time_min": total_dur,
            "packages_delivered": n_pkgs,
        })

    # Write outputs
    save_csv(
        os.path.join(out_dir, "stops_order.csv"),
        ["route_id", "vehicle_id", "stop_position_in_order", "location_id",
         "delivered_id", "arrival_time", "departure_time"],
        stops_rows,
    )
    save_csv(
        os.path.join(out_dir, "undeliverable.csv"),
        ["package_id", "reason"],
        undeliverable,
    )
    save_csv(
        os.path.join(out_dir, "summary.csv"),
        ["vehicle_id", "total_distance_km", "total_time_min", "packages_delivered"],
        summary_rows,
    )

    delivered = sum(len(r.packages) for r in routes)
    print(f"Done: {delivered} delivered, {len(undeliverable)} undeliverable.")


if __name__ == "__main__":
    main()
