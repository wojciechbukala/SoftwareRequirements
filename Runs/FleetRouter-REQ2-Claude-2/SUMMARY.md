```
python3 -m fleetrouter --input <input_dir> --output <output_dir>
```

## Overview

FleetRouter is a command-line daily route planning tool for courier companies. It reads four CSV input files, assigns packages to vehicles under multiple constraints, optimizes routes, and writes three CSV output files.

## Architecture

The implementation is a Python package under `fleetrouter/` with five modules:

| Module | Responsibility |
|---|---|
| `models.py` | Data classes (`Package`, `Vehicle`, `Location`, `StopInfo`, `RouteResult`) and time utilities |
| `reader.py` | Reads and validates all four input CSV files; reports invalid rows and returns pre-classified undeliverables |
| `solver.py` | Greedy best-insertion assignment + 2-opt route optimization |
| `writer.py` | Writes `stops_order.csv`, `summary.csv`, and `undeliverable.csv` |
| `cli.py` | Argument parsing, orchestration, and completion summary line |

## Algorithm

**Assignment (greedy best-insertion):**
1. Packages are sorted by priority descending (priority=1 first), then by `tw_close` ascending (tighter windows first) to minimize infeasible assignments.
2. For each package, every vehicle and every insertion position in that vehicle's current route is evaluated. The (vehicle, position) pair that minimizes marginal additional distance while satisfying all constraints is chosen.
3. Constraints checked per insertion: cumulative weight ≤ `max_weight_kg`, cumulative volume ≤ `max_volume_m3`, arrival within time window at each stop, total route duration ≤ 480 minutes (8 hours). Missing distance entries return `UNREACHABLE`.

**Route optimization (2-opt):**
After all packages are assigned, each vehicle's route is improved by iterative 2-opt: all segment reversals are evaluated, the best feasibility-preserving swap is applied, and the process repeats until no improving swap exists.

**Undeliverable reason selection:**
If a package cannot be assigned to any vehicle, the failure reason is derived from the constraint that blocked it: `UNREACHABLE` if no vehicle could establish a route to the destination, otherwise the highest-priority constraint from `CAPACITY_WEIGHT > CAPACITY_VOLUME > TIME_WINDOW > MAX_DRIVER_TIME > NO_VEHICLE`.

## Input Validation

| Issue | Behaviour |
|---|---|
| Missing input file | Prints error, exits with code 1 |
| Unknown location ID in packages/vehicles | Reported to stderr, row excluded |
| Invalid priority value (not 0 or 1) | Reported to stderr, row excluded |
| `tw_close ≤ tw_open` | Written to `undeliverable.csv` as `TIME_WINDOW` |
| Missing distance entry during routing | Package recorded as `UNREACHABLE` |

## Key Constants

- Depot departure time: **08:00** (480 minutes from midnight, per DA-04)
- Maximum driver working time: **8 hours** (480 minutes, per FR-03)

## Output Files

- **`stops_order.csv`** — one row per stop per route, sorted by vehicle and stop position; vehicles with no deliveries are omitted
- **`summary.csv`** — one row per vehicle (including vehicles with zero deliveries); `total_distance_km` rounded to 2 decimal places, `total_time_min` is the full door-to-door route duration
- **`undeliverable.csv`** — one row per undeliverable package with exactly one reason code

## Running

```bash
# Direct module invocation (no installation required)
python3 -m fleetrouter --input /path/to/input --output /path/to/output

# After installing via pip
pip install -e /path/to/project
fleetrouter --input /path/to/input --output /path/to/output
```
