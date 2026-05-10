# FleetRouter — Implementation Summary

## Overview

FleetRouter is a Python command-line application that produces a daily delivery plan for a courier fleet. It reads four CSV input files, assigns packages to vehicles respecting all constraints, optimises routes, and writes three CSV output files.

## How to Run

```bash
# From the repository root (no installation required)
python3 -m fleetrouter --input <input_dir> --output <output_dir>

# Or via the shell wrapper
./fleetrouter.sh --input <input_dir> --output <output_dir>
```

To install as a system command via pip:

```bash
pip install .
fleetrouter --input <input_dir> --output <output_dir>
```

## Project Structure

```
fleetrouter/
  __init__.py      – package marker
  __main__.py      – CLI entry point and orchestration
  models.py        – dataclasses (Package, Vehicle, Location, DistanceEntry) and time helpers
  reader.py        – CSV ingestion and input validation (FR-01, FR-02)
  planner.py       – package assignment and route optimisation (FR-03, FR-04, FR-05)
  writer.py        – CSV output generation (FR-06)
pyproject.toml     – package metadata and console_scripts entry point
fleetrouter.sh     – convenience wrapper (no installation needed)
```

## Algorithm

### Construction — Best Insertion Heuristic (FR-03, FR-04)

Packages are sorted with **priority=1 first**, then by earliest time-window opening. For each package the planner tries every insertion position in every vehicle's partial route and selects the position that adds the least total distance, subject to:

- cumulative weight ≤ `max_weight_kg` (else `CAPACITY_WEIGHT`)
- cumulative volume ≤ `max_volume_m3` (else `CAPACITY_VOLUME`)
- service must start before `tw_close` (else `TIME_WINDOW`)
- total route duration ≤ 8 hours from 08:00 (else `MAX_DRIVER_TIME`)
- required distance entry must exist (else `UNREACHABLE`); consecutive stops at the same location use distance=0, travel_time=0

If no vehicle can accept a package the most constraining blocking reason is reported in `undeliverable.csv`.

### Optimisation — 2-opt + or-opt (FR-05)

After construction, each vehicle route is improved by:

1. **2-opt** — iteratively reverses sub-sequences when doing so reduces total distance (or, on a tie, total time) without violating any constraint.
2. **or-opt** — iteratively relocates individual stops to cheaper positions.

Both passes repeat until no improving move is found.

### Global objective (FR-05)

Total distance across all vehicles is minimised during construction (cheapest insertion) and further reduced during local search. Route duration is the secondary tie-breaker.

## Input Validation (FR-01, FR-02)

| Check | Effect |
|---|---|
| Any input file missing | Print error, exit 1 |
| Vehicle or package references unknown location | Warning printed, row excluded |
| Package `priority` not in {0, 1} | Warning printed, row excluded |
| `tw_close <= tw_open` | Package recorded in `undeliverable.csv` as `TIME_WINDOW` |

## Output Files (FR-06, Section 3.5)

| File | Content |
|---|---|
| `stops_order.csv` | One row per stop: route_id, vehicle_id, stop_position_in_order, location_id, delivery_package_id, arrival_time, departure_time |
| `summary.csv` | One row per vehicle (including vehicles with no deliveries): vehicle_id, total_distance_km, total_time_min, packages_delivered |
| `undeliverable.csv` | One row per undeliverable package: package_id, reason |

Times are formatted as HH:MM. Distances are rounded to two decimal places. Durations are integer minutes.

## Design Notes

- **DA-04**: All vehicles depart their depot at **08:00** (hardcoded constant `START_TIME_MIN = 480`).
- Same-location consecutive stops use 0 km / 0 min rather than requiring a self-loop entry in `distances.csv`.
- Reason priority when multiple constraints block a package: `UNREACHABLE > CAPACITY_WEIGHT > CAPACITY_VOLUME > TIME_WINDOW > MAX_DRIVER_TIME > NO_VEHICLE`.
- The code uses only Python standard library — no external dependencies.
