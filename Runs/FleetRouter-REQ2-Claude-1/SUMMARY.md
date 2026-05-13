```
python3 -m fleetrouter --input <input_dir> --output <output_dir>
```

## Overview

FleetRouter is a Python 3 command-line application that performs daily route planning for courier companies. It reads four input CSV files, assigns packages to vehicles under all specified constraints, optimizes routes to minimize total fleet distance, and writes three output CSV files.

## Architecture

The system is implemented as a Python package (`fleetrouter/`) with the following modules:

| Module | Responsibility |
|---|---|
| `models.py` | Data classes: `Package`, `Vehicle`, `Location`, `RouteStop`, `VehicleRoute`; time conversion utilities |
| `reader.py` | CSV parsing and input validation for all four input files |
| `planner.py` | Package assignment (best-insertion heuristic) and route optimization (2-opt) |
| `writer.py` | Output CSV generation for `stops_order.csv`, `summary.csv`, `undeliverable.csv` |
| `__main__.py` | CLI entry point (`--input`, `--output` arguments), orchestration, and progress reporting |

## Algorithm

### Assignment (FR-03)
Packages are sorted by **priority descending** (priority=1 first), then **time-window open ascending** (tighter windows first). For each package, the algorithm tries every vehicle and every insertion position in that vehicle's current route sequence, choosing the vehicle+position with the **minimum additional total distance** (tie-broken by minimum additional time). Constraint checks: weight capacity, volume capacity, time-window feasibility (arrival ≤ `tw_close`), and 8-hour driver time limit.

### Timing model (FR-04, DA-04)
All vehicles depart their depot at **08:00** (480 min from midnight). At each stop:
- `arrival = previous_departure + travel_time`
- `departure = max(arrival, tw_open) + service_min`

The vehicle returns to its depot after the last stop. Total route duration = depot-to-depot elapsed time.

### Route optimization (FR-05)
After all packages are assigned, each vehicle's stop sequence is improved with **2-opt local search** (first-improvement strategy). Only moves that produce a feasible route (all time windows satisfied, driver time ≤ 8 h) are accepted. Primary criterion: minimize total distance; secondary: minimize total duration.

### Undeliverable reason priority (FR-02, FR-03)
When a package cannot be assigned, the most specific reason is reported using this priority: `UNREACHABLE` > `TIME_WINDOW` > `MAX_DRIVER_TIME` > `CAPACITY_WEIGHT` > `CAPACITY_VOLUME` > `NO_VEHICLE`.

## Input / Output

**Inputs** (all mandatory, UTF-8 CSV):
- `packages.csv` — package_id, destination_id, weight_kg, volume_m3, tw_open, tw_close, service_min, priority
- `vehicles.csv` — vehicle_id, max_weight_kg, max_volume_m3, depot_location_id
- `locations.csv` — location_id, name
- `distances.csv` — from_location_id, to_location_id, distance_km, travel_time_min

**Outputs** (UTF-8 CSV):
- `stops_order.csv` — route_id, vehicle_id, stop_position_in_order, location_id, delivery_package_id, arrival_time, departure_time
- `summary.csv` — vehicle_id, total_distance_km, total_time_min, packages_delivered (all vehicles included)
- `undeliverable.csv` — package_id, reason

## Design decisions

- **Note on column name:** FR-06 names the package column `delivery_package_id`, while section 3.5 lists it as `delivered_id`. The implementation uses `delivery_package_id` as specified in the functional requirement section.
- `route_id` in `stops_order.csv` equals `vehicle_id` since each vehicle has exactly one daily route (DA-04).
- Distance comparisons use a floating-point epsilon (1e-9) to avoid precision artifacts.
- No third-party dependencies — standard library only (`csv`, `argparse`, `pathlib`, `dataclasses`).
