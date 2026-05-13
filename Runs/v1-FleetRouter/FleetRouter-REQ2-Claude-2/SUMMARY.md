# FleetRouter — Implementation Summary

## Overview

FleetRouter is a command-line route-planning tool for courier companies. It reads four CSV
input files, assigns packages to vehicles while respecting all constraints, constructs and
optimises daily delivery routes, and writes three CSV output files.

## Invocation

```
./fleetrouter --input <input-dir> --output <output-dir>
```

Both arguments are mandatory. The program terminates with a non-zero exit code and an
error message if any required input file is missing.

## File Structure

```
fleetrouter              — executable entry-point script
fleet_router/
    __init__.py
    models.py            — data classes (Package, Vehicle, Location, DistanceEntry, Stop, Route)
    reader.py            — CSV input parsing
    validator.py         — input validation (location references, time windows)
    planner.py           — package assignment, route construction, 2-opt/or-opt optimisation
    writer.py            — CSV output generation
    cli.py               — argument parsing and main control flow
```

## Algorithm

### Assignment (`planner.py`)

Packages are sorted by **priority descending**, then by **time-window close ascending** so
that high-priority and time-critical packages get first access to vehicle capacity.

For each package, every vehicle is tested. Capacity (weight, then volume) is checked first.
For vehicles with sufficient capacity, a **best-insertion heuristic** tries every insertion
position in the vehicle's current route and accepts the one with the minimum added distance
that passes the full route simulation (travel times, time windows, 8-hour driver limit).

The package is assigned to the vehicle whose best insertion adds the least total distance.

### Route Simulation

`simulate_route` replays the full route from depot (departure 08:00) through all stops and
back, computing per-stop arrival, optional wait, and departure times, total driven distance,
and total route duration. It returns a failure reason
(`UNREACHABLE`, `TIME_WINDOW`, `MAX_DRIVER_TIME`) on the first constraint violation.

### Optimisation (`planner.py`)

After all packages are assigned, each vehicle's route undergoes iterative local search:

1. **2-opt** — try all segment-reversal pairs; accept the first improving swap.
2. **or-opt** (single-stop relocation) — try moving each stop to every other position;
   accept the first improving move.

Both passes are repeated until no further improvement is found. Every candidate is validated
by `simulate_route` to ensure all time-window and driver-time constraints remain satisfied.
The primary objective is minimum total distance; total duration breaks ties.

### Undeliverable Reason Assignment

| Condition | Reason |
|---|---|
| `tw_close ≤ tw_open` (pre-validation) | `TIME_WINDOW` |
| All vehicles fail weight capacity | `CAPACITY_WEIGHT` |
| All vehicles fail volume capacity | `CAPACITY_VOLUME` |
| All feasible insertions have missing distance entries | `UNREACHABLE` |
| Time window cannot be met on any capable vehicle | `TIME_WINDOW` |
| Route would exceed 8 hours on any capable vehicle | `MAX_DRIVER_TIME` |
| No other specific constraint | `NO_VEHICLE` |

## Output Files

| File | Contents |
|---|---|
| `stops_order.csv` | Ordered stops per vehicle: route_id, vehicle_id, stop_position_in_order, location_id, delivery_package_id, arrival_time, departure_time |
| `summary.csv` | Per-vehicle totals (all vehicles included): total_distance_km, total_time_min, packages_delivered |
| `undeliverable.csv` | Packages that could not be assigned: package_id, reason |

Times are formatted `HH:MM`; distances are rounded to two decimal places; durations are
integer minutes.

## Constants

- Depot departure time: **08:00** (480 minutes from midnight)
- Maximum driver time: **8 hours** (480 minutes)
- Priority values: **0** (standard) or **1** (priority); other values are excluded with a warning

## Design Notes

- No external dependencies — standard library only (`csv`, `argparse`, `os`, `sys`)
- Clean separation of concerns across modules
- All time values are stored internally as integer minutes from midnight
- The `simulate_route` function is the single source of truth for route feasibility
