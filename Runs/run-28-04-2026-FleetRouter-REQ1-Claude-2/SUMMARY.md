# FleetRouter — Implementation Summary

## Overview

FleetRouter is a command-line tool for daily route planning for a courier company. It reads input CSV files, assigns packages to vehicles, computes optimised routes, and writes the results to output CSV files.

## Usage

```
fleetrouter --input <input_dir> --output <output_dir>
```

For environments where direct installation isn't available:

```
PYTHONPATH=/workspace python3 -m fleetrouter.main --input <input_dir> --output <output_dir>
```

## Project Structure

```
fleetrouter/
  __init__.py     — package marker
  models.py       — data classes (Package, Vehicle, Location, Route, Stop) and time helpers
  io.py           — flexible CSV readers (multi-alias column names) and output writers
  main.py         — CLI entry point, input validation, orchestration
  router.py       — routing engine: greedy insertion + 2-opt optimisation
pyproject.toml    — pip-installable package definition (entry point: fleetrouter)
setup.py          — legacy setup for broader pip compatibility
bin/fleetrouter   — standalone executable wrapper
```

## Algorithm

### Input Validation

1. **Location references** — packages or vehicles referencing unknown location IDs are excluded and warned.
2. **Time windows** — packages where `time_open >= time_close` are recorded as `TIME_WINDOW` undeliverable.
3. **Unreachability** — packages for which no vehicle's depot has both an outbound and inbound distance entry are recorded as `UNREACHABLE`.

### Route Planning

1. **Sorting** — packages are sorted: priority=True first, then by `time_close` (urgency), then `time_open`.
2. **Greedy cheapest insertion** — for each package, every vehicle and every insertion position is tried. The insertion that minimises additional distance (then additional duration) is chosen, subject to:
   - Weight capacity constraint
   - Volume capacity constraint
   - Time window feasibility (arrival ≤ `time_close`)
   - Maximum driver time (≤ 480 minutes total)
   - Existence of all required distance entries
3. **2-opt optimisation** — after all packages are assigned, each route is improved by iteratively swapping pairs of edges until no improvement remains (minimise distance first, then duration).

### Undeliverable Reason Codes

When no insertion is feasible for a package, the reason is determined by precedence:

| Code | Condition |
|------|-----------|
| `CAPACITY_WEIGHT` | No vehicle has sufficient remaining weight capacity |
| `CAPACITY_VOLUME` | No vehicle has sufficient remaining volume capacity |
| `TIME_WINDOW` | Earliest direct arrival from any depot exceeds `time_close` |
| `MAX_DRIVER_TIME` | All valid insertions would exceed 8-hour driver limit |
| `UNREACHABLE` | No vehicle can reach the destination from its depot |
| `NO_VEHICLE` | Fallback when none of the above applies |

### Same-Location Optimisation

When two packages share a delivery location, the travel distance between them is treated as zero, allowing them to be serviced consecutively without extra travel cost.

## Output Files

| File | Contents |
|------|----------|
| `stops_order.csv` | route_id, vehicle_id, stop_order, location_id, package_id, arrival_time, departure_time (HH:MM); includes depot start/end stops |
| `undeliverable.csv` | package_id, reason |
| `summary.csv` | vehicle_id, total_distance (km, 2 d.p.), total_duration (integer minutes), packages_delivered |

## CSV Column Name Flexibility

The reader accepts multiple common column name variants (e.g. `from_id`, `from`, `origin`, `from_location` are all accepted for the distances "from" column), making the system robust to different naming conventions.
