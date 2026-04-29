"""FleetRouter — daily route planning for a courier company."""

import argparse
import csv
import os
import sys
from typing import Dict, List, Optional, Tuple

DEPOT_TIME = 480       # 08:00 in minutes from midnight
MAX_DRIVER_MIN = 480   # 8-hour work day


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def time_to_min(t: str) -> int:
    h, m = t.strip().split(":")
    return int(h) * 60 + int(m)


def min_to_time(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


# ---------------------------------------------------------------------------
# Route simulation
# ---------------------------------------------------------------------------

def _leg(distances: Dict, from_loc: str, to_loc: str) -> Optional[Dict]:
    """Return travel leg dict; same-location travel is always (0 km, 0 min)."""
    if from_loc == to_loc:
        return {"distance": 0.0, "travel_time": 0}
    return distances.get((from_loc, to_loc))


def simulate_route(
    depot: str,
    stops: List[Dict],
    distances: Dict,
) -> Optional[Dict]:
    """
    Simulate a route starting and ending at *depot*.

    Returns a dict with keys ``stop_times``, ``total_distance``, and
    ``total_duration``, or *None* if the route is infeasible for any reason
    (missing distance entry, time-window violation, or driver-time exceeded).
    """
    if not stops:
        return {"stop_times": [], "total_distance": 0.0, "total_duration": 0}

    current_loc = depot
    current_time = DEPOT_TIME
    total_distance = 0.0
    stop_times: List[Dict] = []

    for stop in stops:
        leg = _leg(distances, current_loc, stop["location_id"])
        if leg is None:
            return None

        arrival = current_time + leg["travel_time"]
        serve_start = max(arrival, stop["tw_open_min"])

        if serve_start > stop["tw_close_min"]:
            return None  # time-window violated

        departure = serve_start + stop["service_duration"]
        stop_times.append({"arrival": arrival, "departure": departure})

        total_distance += leg["distance"]
        current_time = departure
        current_loc = stop["location_id"]

    # Return leg
    leg = distances.get((current_loc, depot))
    if leg is None:
        return None

    total_distance += leg["distance"]
    end_time = current_time + leg["travel_time"]
    total_duration = end_time - DEPOT_TIME

    if total_duration > MAX_DRIVER_MIN:
        return None  # driver-time exceeded

    return {
        "stop_times": stop_times,
        "total_distance": total_distance,
        "total_duration": total_duration,
    }


def check_time_windows_only(depot: str, stops: List[Dict], distances: Dict) -> bool:
    """
    Return True if all time windows can be met (ignores driver-time limit).
    Used to distinguish TIME_WINDOW from MAX_DRIVER_TIME failure.
    """
    current_loc = depot
    current_time = DEPOT_TIME

    for stop in stops:
        leg = _leg(distances, current_loc, stop["location_id"])
        if leg is None:
            return False
        arrival = current_time + leg["travel_time"]
        serve_start = max(arrival, stop["tw_open_min"])
        if serve_start > stop["tw_close_min"]:
            return False
        departure = serve_start + stop["service_duration"]
        current_time = departure
        current_loc = stop["location_id"]

    return _leg(distances, current_loc, depot) is not None


# ---------------------------------------------------------------------------
# 2-opt local-search improvement
# ---------------------------------------------------------------------------

def two_opt(depot: str, stops: List[Dict], distances: Dict) -> Tuple[List[Dict], Dict]:
    """
    Apply 2-opt exchanges to minimise total_distance, then total_duration.
    Returns the (possibly improved) stop list and its simulation result.
    """
    best = stops[:]
    best_res = simulate_route(depot, best, distances)
    if best_res is None:
        return stops, {"stop_times": [], "total_distance": float("inf"), "total_duration": 0}

    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 2, len(best)):
                candidate = best[: i + 1] + list(reversed(best[i + 1 : j + 1])) + best[j + 1 :]
                res = simulate_route(depot, candidate, distances)
                if res is None:
                    continue
                if res["total_distance"] < best_res["total_distance"] or (
                    res["total_distance"] == best_res["total_distance"]
                    and res["total_duration"] < best_res["total_duration"]
                ):
                    best = candidate
                    best_res = res
                    improved = True

    return best, best_res


# ---------------------------------------------------------------------------
# Reason determination for undeliverable packages
# ---------------------------------------------------------------------------

def determine_reason(
    pkg: Dict,
    vehicles: List[Dict],
    vehicle_stops: Dict[str, List[Dict]],
    distances: Dict,
) -> str:
    """Return the single best reason code for why *pkg* cannot be delivered."""

    # Weight capacity: is there ANY vehicle with enough remaining weight?
    weight_ok = [
        v for v in vehicles
        if sum(s["weight"] for s in vehicle_stops[v["vehicle_id"]]) + pkg["weight"]
        <= v["max_weight"]
    ]
    if not weight_ok:
        return "CAPACITY_WEIGHT"

    # Volume capacity: among weight-ok vehicles, any with enough volume?
    vol_ok = [
        v for v in weight_ok
        if sum(s["volume"] for s in vehicle_stops[v["vehicle_id"]]) + pkg["volume"]
        <= v["max_volume"]
    ]
    if not vol_ok:
        return "CAPACITY_VOLUME"

    # Try insertion into capacity-feasible vehicles
    # If time windows are satisfiable without driver-time limit → MAX_DRIVER_TIME
    # Otherwise → TIME_WINDOW (or UNREACHABLE for missing distances)
    for veh in vol_ok:
        vid = veh["vehicle_id"]
        depot = veh["depot_location_id"]
        stops = vehicle_stops[vid]

        for i in range(len(stops) + 1):
            candidate = stops[:i] + [pkg] + stops[i:]
            if check_time_windows_only(depot, candidate, distances):
                # Time windows are fine without the driver limit → driver time is the issue
                return "MAX_DRIVER_TIME"

    # Check whether the issue is a missing distance entry (UNREACHABLE)
    # or simply that time windows cannot be met (TIME_WINDOW)
    for veh in vol_ok:
        vid = veh["vehicle_id"]
        depot = veh["depot_location_id"]
        stops = vehicle_stops[vid]

        for i in range(len(stops) + 1):
            candidate = stops[:i] + [pkg] + stops[i:]
            current_loc = depot
            current_time = DEPOT_TIME
            missing_dist = False
            tw_fail = False

            for stop in candidate:
                leg = _leg(distances, current_loc, stop["location_id"])
                if leg is None:
                    missing_dist = True
                    break
                arrival = current_time + leg["travel_time"]
                serve_start = max(arrival, stop["tw_open_min"])
                if serve_start > stop["tw_close_min"]:
                    tw_fail = True
                    break
                current_time = serve_start + stop["service_duration"]
                current_loc = stop["location_id"]

            if missing_dist:
                return "UNREACHABLE"
            if tw_fail:
                return "TIME_WINDOW"

    return "NO_VEHICLE"


# ---------------------------------------------------------------------------
# Main routing logic
# ---------------------------------------------------------------------------

def plan(input_dir: str, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)

    # --- Load data ----------------------------------------------------------

    locations: Dict[str, str] = {}
    with open(os.path.join(input_dir, "locations.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            locations[row["location_id"]] = row["name"]

    distances: Dict[Tuple[str, str], Dict] = {}
    with open(os.path.join(input_dir, "distances.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            key = (row["from_location_id"], row["to_location_id"])
            distances[key] = {
                "distance": float(row["distance"]),
                "travel_time": int(row["travel_time"]),
            }

    raw_packages: List[Dict] = []
    with open(os.path.join(input_dir, "packages.csv"), newline="") as fh:
        raw_packages = list(csv.DictReader(fh))

    raw_vehicles: List[Dict] = []
    with open(os.path.join(input_dir, "vehicles.csv"), newline="") as fh:
        raw_vehicles = list(csv.DictReader(fh))

    # --- Validate & filter --------------------------------------------------

    undeliverable: List[Dict] = []

    # Vehicles with invalid depot are silently excluded
    vehicles: List[Dict] = []
    for r in raw_vehicles:
        if r["depot_location_id"] in locations:
            vehicles.append(
                {
                    "vehicle_id": r["vehicle_id"],
                    "max_weight": float(r["max_weight"]),
                    "max_volume": float(r["max_volume"]),
                    "depot_location_id": r["depot_location_id"],
                }
            )

    packages: List[Dict] = []
    for r in raw_packages:
        pid = r["package_id"]

        # Invalid delivery location → silently excluded (not added to undeliverable)
        if r["location_id"] not in locations:
            continue

        # Invalid time window
        try:
            tw_open = time_to_min(r["time_window_open"])
            tw_close = time_to_min(r["time_window_close"])
        except Exception:
            undeliverable.append({"package_id": pid, "reason": "TIME_WINDOW"})
            continue

        if tw_open >= tw_close:
            undeliverable.append({"package_id": pid, "reason": "TIME_WINDOW"})
            continue

        packages.append(
            {
                "package_id": pid,
                "location_id": r["location_id"],
                "weight": float(r["weight"]),
                "volume": float(r["volume"]),
                "tw_open": r["time_window_open"],
                "tw_close": r["time_window_close"],
                "tw_open_min": tw_open,
                "tw_close_min": tw_close,
                "service_duration": int(r["service_duration"]),
                "priority": r["priority"].strip().lower() in ("true", "1", "yes"),
            }
        )

    # UNREACHABLE: package destination must be reachable from at least one depot
    depot_locs = {v["depot_location_id"] for v in vehicles}
    valid_packages: List[Dict] = []
    for pkg in packages:
        loc = pkg["location_id"]
        reachable = any(
            (d, loc) in distances and (loc, d) in distances for d in depot_locs
        )
        if not reachable:
            undeliverable.append({"package_id": pkg["package_id"], "reason": "UNREACHABLE"})
        else:
            valid_packages.append(pkg)
    packages = valid_packages

    # Sort: priority first, then earliest closing time (tightest deadline first)
    packages.sort(key=lambda p: (not p["priority"], p["tw_close_min"]))

    # --- Greedy cheapest-insertion assignment --------------------------------

    vehicle_stops: Dict[str, List[Dict]] = {v["vehicle_id"]: [] for v in vehicles}

    for pkg in packages:
        best_vid: Optional[str] = None
        best_pos: Optional[int] = None
        best_added_dist = float("inf")
        best_added_dur = float("inf")

        for veh in vehicles:
            vid = veh["vehicle_id"]
            depot = veh["depot_location_id"]
            stops = vehicle_stops[vid]

            # Capacity pre-check
            used_w = sum(s["weight"] for s in stops)
            used_v = sum(s["volume"] for s in stops)
            if used_w + pkg["weight"] > veh["max_weight"]:
                continue
            if used_v + pkg["volume"] > veh["max_volume"]:
                continue

            curr_res = simulate_route(depot, stops, distances)
            curr_dist = curr_res["total_distance"] if curr_res else 0.0
            curr_dur = curr_res["total_duration"] if curr_res else 0

            for i in range(len(stops) + 1):
                candidate = stops[:i] + [pkg] + stops[i:]
                res = simulate_route(depot, candidate, distances)
                if res is None:
                    continue

                added_dist = res["total_distance"] - curr_dist
                added_dur = res["total_duration"] - curr_dur

                if added_dist < best_added_dist or (
                    added_dist == best_added_dist and added_dur < best_added_dur
                ):
                    best_vid = vid
                    best_pos = i
                    best_added_dist = added_dist
                    best_added_dur = added_dur

        if best_vid is not None:
            vehicle_stops[best_vid].insert(best_pos, pkg)
        else:
            reason = determine_reason(pkg, vehicles, vehicle_stops, distances)
            undeliverable.append({"package_id": pkg["package_id"], "reason": reason})

    # --- 2-opt improvement --------------------------------------------------

    final_results: Dict[str, Dict] = {}
    for veh in vehicles:
        vid = veh["vehicle_id"]
        depot = veh["depot_location_id"]
        stops = vehicle_stops[vid]

        if len(stops) >= 2:
            stops, res = two_opt(depot, stops, distances)
            vehicle_stops[vid] = stops
        else:
            res = simulate_route(depot, stops, distances) or {
                "stop_times": [],
                "total_distance": 0.0,
                "total_duration": 0,
            }

        final_results[vid] = res

    # --- Write output --------------------------------------------------------

    stops_rows: List[Dict] = []
    summary_rows: List[Dict] = []
    route_id = 1

    for veh in vehicles:
        vid = veh["vehicle_id"]
        depot = veh["depot_location_id"]
        stops = vehicle_stops[vid]
        res = final_results[vid]

        order = 0

        # Depot departure row
        stops_rows.append(
            {
                "route_id": route_id,
                "vehicle_id": vid,
                "stop_order": order,
                "location_id": depot,
                "package_id": "",
                "arrival_time": min_to_time(DEPOT_TIME),
                "departure_time": min_to_time(DEPOT_TIME),
            }
        )
        order += 1

        for stop, times in zip(stops, res["stop_times"]):
            stops_rows.append(
                {
                    "route_id": route_id,
                    "vehicle_id": vid,
                    "stop_order": order,
                    "location_id": stop["location_id"],
                    "package_id": stop["package_id"],
                    "arrival_time": min_to_time(times["arrival"]),
                    "departure_time": min_to_time(times["departure"]),
                }
            )
            order += 1

        # Depot return row
        if stops:
            last_loc = stops[-1]["location_id"]
            last_dep = res["stop_times"][-1]["departure"]
            ret_leg = _leg(distances, last_loc, depot)
            ret_arr = last_dep + ret_leg["travel_time"] if ret_leg else last_dep
        else:
            ret_arr = DEPOT_TIME

        stops_rows.append(
            {
                "route_id": route_id,
                "vehicle_id": vid,
                "stop_order": order,
                "location_id": depot,
                "package_id": "",
                "arrival_time": min_to_time(ret_arr),
                "departure_time": min_to_time(ret_arr),
            }
        )

        summary_rows.append(
            {
                "vehicle_id": vid,
                "total_distance": f"{res['total_distance']:.2f}",
                "total_duration": res["total_duration"],
                "packages_delivered": len(stops),
            }
        )

        route_id += 1

    _write_csv(
        os.path.join(output_dir, "stops_order.csv"),
        ["route_id", "vehicle_id", "stop_order", "location_id", "package_id",
         "arrival_time", "departure_time"],
        stops_rows,
    )
    _write_csv(
        os.path.join(output_dir, "undeliverable.csv"),
        ["package_id", "reason"],
        undeliverable,
    )
    _write_csv(
        os.path.join(output_dir, "summary.csv"),
        ["vehicle_id", "total_distance", "total_duration", "packages_delivered"],
        summary_rows,
    )


def _write_csv(path: str, fieldnames: List[str], rows: List[Dict]) -> None:
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fleetrouter",
        description="FleetRouter — daily courier route planner",
    )
    parser.add_argument("--input", required=True, metavar="DIR",
                        help="directory containing input CSV files")
    parser.add_argument("--output", required=True, metavar="DIR",
                        help="directory where output CSV files are written")
    args = parser.parse_args()

    try:
        plan(args.input, args.output)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
