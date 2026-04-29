# FleetRouter – Implementation Summary

## Overview

FleetRouter is a Python 3 command-line program that plans daily delivery routes for a courier company, satisfying all constraints defined in the Alloy model and the operational requirements.

```
python main.py [input_dir [output_dir]]
```

Both directories default to the current working directory. Input files (`packages.csv`, `vehicles.csv`, `locations.csv`, `distances.csv`) are read from `input_dir`; output files (`stops_order.csv`, `undeliverable.csv`, `summary.csv`) are written to `output_dir`.

## File Structure

| File | Role |
|---|---|
| `main.py` | Entry point; wires I/O and planning together |
| `models.py` | Immutable data classes (`Location`, `Package`, `Vehicle`, `RouteStop`, `Route`, `InputData`, `PlanResult`) |
| `io_handler.py` | CSV parsing with validation, time conversion (`HH:MM` ↔ minutes since 08:00), and output writing |
| `validator.py` | Inherent-undeliverability checks, one function per Alloy predicate |
| `planner.py` | VRP solver: greedy cheapest-insertion + 2-opt improvement |

## Algorithm

### 1. Input Parsing and Validation
All four CSV files are read with UTF-8 encoding. Rows with malformed data (invalid numeric fields, unknown location references, `priority` values outside `{0,1}`, negative weights/volumes, `tw_close ≤ tw_open`) are silently excluded from planning.

### 2. Inherent Undeliverability (validator.py)
Before routing, each package is tested against the Alloy model predicates in priority order:

| Checked first | Reason code |
|---|---|
| No vehicles exist | `NO_VEHICLE` |
| No route from any depot to destination (or back) | `UNREACHABLE` |
| Package weight exceeds every vehicle's capacity | `CAPACITY_WEIGHT` |
| Package volume exceeds every vehicle's capacity | `CAPACITY_VOLUME` |
| Earliest possible arrival > `tw_close` for all vehicles | `TIME_WINDOW` |
| Minimum round-trip time (outbound + service + inbound) > 480 min for all vehicles | `MAX_DRIVER_TIME` |

### 3. Route Construction – Greedy Cheapest Insertion
Remaining deliverable packages are assigned in two passes:

- **Pass 1 – priority packages** (`priority = 1`), sorted by `tw_close` ascending (tightest deadline first).
- **Pass 2 – non-priority packages** (`priority = 0`), same sort order.

This ordering guarantees the priority invariant: a non-priority package is never inserted before a priority package has had the opportunity to claim vehicle capacity. If a non-priority package cannot fit after all priority packages are placed, it is reported as `NO_VEHICLE`.

For each package the planner evaluates every insertion position in every vehicle's current route, choosing the position that minimises the additional distance driven. Feasibility checks enforce:
- Combined weight ≤ vehicle `max_weight_kg`
- Combined volume ≤ vehicle `max_volume_m3`
- All time windows (`arrival ≤ tw_close`) and correct wait-then-serve timing
- Total driver time (return to depot) ≤ 480 minutes

### 4. Route Improvement – 2-opt
After construction, each route is improved independently with 2-opt: adjacent segment reversals are accepted whenever they strictly reduce total route distance and remain time-feasible, and the loop repeats until no improving swap exists.

### 5. Optimality Objective
The greedy cheapest-insertion heuristic directly minimises marginal distance at each insertion step. The 2-opt pass further reduces total distance. In the event of a distance tie between insertion candidates, the vehicle with the shorter current route is preferred (indirectly reducing total duration).

## Output Format

- **`stops_order.csv`** – One row per stop per route: depot-start (position 1), delivery stops (positions 2…n+1), depot-end (position n+2). Times in `HH:MM`. `delivered_id` is empty for depot stops.
- **`undeliverable.csv`** – One row per undeliverable package with the Alloy reason code.
- **`summary.csv`** – One row per vehicle. `total_distance_km` rounded to two decimal places; `total_time_min` is elapsed integer minutes from 08:00 to depot return.

## Constraints Satisfied

| Requirement | How satisfied |
|---|---|
| G-01: every package delivered or marked undeliverable | Two-pass insertion + undeliverability detection |
| G-02: undeliverable packages reported with reason | `validator.py` + `NO_VEHICLE` fallback |
| G-03: minimise total distance (tiebreak: duration) | Cheapest-insertion construction + 2-opt improvement |
| Priority rule | Priority packages inserted in Pass 1 before any non-priority package |
| Time windows | Checked in every feasibility evaluation |
| Capacity (weight & volume) | Checked before each insertion |
| Driver time ≤ 480 min | Checked in route simulation |
| Asymmetric distances | Distance matrix keyed by `(from_id, to_id)` |
| Scale: 500 packages, 50 vehicles, 200 locations | O(n·V·k) insertion loop; O(k²) 2-opt per route |
