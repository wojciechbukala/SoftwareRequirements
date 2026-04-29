# FleetRouter — Implementation Summary

## What was built

A command-line tool called **FleetRouter** that reads courier-company input data from CSV files, assigns packages to vehicles, computes optimised routes, and writes results to CSV output files.

## Invocation

```
fleetrouter --input <input-dir> --output <output-dir>
```

The tool is installed as a console-script entry point via `setup.py`. It can also be run directly with:

```
python3 -m fleetrouter.main --input <input-dir> --output <output-dir>
```

## Files

| Path | Purpose |
|------|---------|
| `fleetrouter/main.py` | Full implementation (~490 lines) |
| `fleetrouter/__init__.py` | Package marker |
| `setup.py` | Install with `pip install -e .` |
| `fleetrouter.sh` | Shell wrapper (no install required) |

## Algorithm

### 1. Input loading & validation
- `locations.csv`, `distances.csv`, `packages.csv`, `vehicles.csv` are read with `csv.DictReader`.
- Vehicles with an unrecognised depot location are silently excluded.
- Packages with an unrecognised delivery location are silently excluded (not reported in `undeliverable.csv`).
- Packages with an invalid time window (open ≥ close) are written to `undeliverable.csv` with reason `TIME_WINDOW`.

### 2. Reachability pre-check (UNREACHABLE)
For each remaining package, at least one vehicle depot must have both a forward distance entry (depot → package location) and a return distance entry (package location → depot). Packages that fail this check are written to `undeliverable.csv` with reason `UNREACHABLE`.

Same-location travel (when two consecutive stops share the same location ID) is treated as 0 km / 0 minutes so that packages with the same delivery location can be batched on one route.

### 3. Greedy cheapest-insertion assignment
Packages are sorted: **priority packages first**, then by earliest time-window closing time (tightest deadline first).

For each package in that order, every vehicle is tried at every insertion position. The position that minimises the added route distance (tie-broken by added duration) is chosen. Capacity (weight and volume), time windows, and the 8-hour driver limit are all enforced by re-simulating the full candidate route after each insertion.

If no vehicle can accommodate a package, `determine_reason()` identifies the single best reason code:
- **CAPACITY_WEIGHT** — no vehicle has enough remaining weight capacity
- **CAPACITY_VOLUME** — no vehicle (that has enough weight) has enough remaining volume capacity
- **MAX_DRIVER_TIME** — capacity is fine but every feasible insertion would exceed the 8-hour limit
- **TIME_WINDOW** — the package's time window cannot be met at any feasible insertion position
- **UNREACHABLE** — a missing distance entry is encountered during route simulation
- **NO_VEHICLE** — none of the above apply (catch-all)

### 4. 2-opt local-search improvement
After all packages are assigned, each vehicle's route is improved with a 2-opt exchange loop. The objective is to minimise total distance, with total duration as a tie-breaker.

### 5. Output generation
- **`stops_order.csv`** — one row per stop (including depot departure and depot return), with route ID, vehicle ID, stop order, location, package (empty for depot rows), arrival time, and departure time.
- **`undeliverable.csv`** — one row per undeliverable package with exactly one reason code.
- **`summary.csv`** — one row per vehicle with total distance (km, 2 decimal places), total duration (integer minutes), and package count.

Every vehicle appears in `summary.csv` and `stops_order.csv` even if it makes no deliveries (zero distance, zero duration).

## Constraints enforced
- Weight and volume capacity limits per vehicle
- Time windows (vehicle waits if it arrives early; fails if it cannot arrive before closing time)
- 8-hour / 480-minute driver work day
- Vehicle departs depot at exactly 08:00
- Route starts and ends at the vehicle's assigned depot
- Priority packages are assigned before non-priority packages
