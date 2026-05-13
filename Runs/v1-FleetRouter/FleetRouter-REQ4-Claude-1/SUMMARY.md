# FleetRouter — Implementation Summary

## Overview

FleetRouter is a Vehicle Routing Problem with Time Windows (VRPTW) solver for courier fleet management. It reads four CSV input files and produces three CSV output files describing the optimal daily delivery plan.

## Files

| File | Purpose |
|---|---|
| `main.py` | Entry point — reads inputs, runs planner, writes outputs |
| `models.py` | Data classes: `Location`, `Package`, `Vehicle`, `Route`, `DeliveryStop`, `DepotStop` |
| `io_handler.py` | CSV parsing and serialisation with full input validation |
| `feasibility.py` | Per-package infeasibility classification for all six reason codes |
| `planner.py` | VRP solver: construction heuristic + 2-opt + Or-opt |

## Algorithm

### Phase 1 — Input parsing and validation
All four CSV files are read and validated. Invalid rows (bad types, negative values, out-of-range priority, unknown location IDs, malformed times) are logged to stderr and excluded from processing.

Time windows (`tw_open`, `tw_close`) are stored internally as **minutes since 08:00** (per the Alloy model comment). HH:MM conversion happens at I/O boundaries only.

### Phase 2 — Individual infeasibility classification (`feasibility.py`)
Each package is checked against all vehicles. A package is inherently infeasible if **every** vehicle fails the relevant predicate. Reason codes are assigned in the following priority order (most fundamental first):

1. `NO_VEHICLE` — no vehicles exist
2. `UNREACHABLE` — no route from any depot to the destination (or back) exists in `distances.csv`
3. `CAPACITY_WEIGHT` — package weight exceeds every vehicle's maximum
4. `CAPACITY_VOLUME` — package volume exceeds every vehicle's maximum
5. `MAX_DRIVER_TIME` — outbound travel + service + return > 480 min for all vehicles
6. `TIME_WINDOW` — earliest possible arrival > `tw_close` for all vehicles

### Phase 3 — VRP optimisation (`planner.py`)
Only packages that passed the individual feasibility check enter the routing phase.

**Construction — cheapest insertion:**
Packages are sorted by priority descending, then `tw_close` ascending (earliest-deadline-first), then weight descending. Processing priority packages first guarantees that when a capacity conflict arises between a priority and a non-priority package, the priority package wins. For each package the solver tries every (route, position) pair and picks the insertion that minimises marginal route distance while satisfying:
- Weight and volume capacity
- Time windows at every stop (waiting is allowed; late arrival is not)
- Driver return by 16:00 (minute 480)
- Route connectivity (distances must exist in `distances.csv`)

If no existing route can absorb the package, a new route is opened on the next available vehicle. If no vehicle remains, the package is written to `undeliverable.csv` with reason `NO_VEHICLE`.

**Local search — 2-opt (within routes):**
After construction, each route is improved by reversing every pair of sub-segments until no further distance reduction is possible. Works correctly with asymmetric distances.

**Local search — Or-opt (between routes):**
Up to 20 passes of single-package relocation between routes. Each move is accepted only when it strictly reduces total fleet distance. After each accepted move, 2-opt is re-applied to the affected routes.

## Constraints honoured

| Constraint | Enforcement |
|---|---|
| Weight / volume capacity | Checked at every insertion attempt |
| Time windows (`twOpen ≤ arrival ≤ twClose`) | Forward time propagation; late arrival rejected |
| Waiting at stops | Vehicle waits if it arrives before `twOpen` |
| Driver time ≤ 480 min | End-of-route time checked at every insertion |
| Route connectivity | Missing distances treated as unreachable edges |
| Each package delivered at most once | Assignment set; no duplicates |
| Priority packages preferred in capacity conflicts | Priority sort order in construction |

## Output formats

- **Time values** (`arrival_time`, `departure_time`, `tw_open`, `tw_close`): `HH:MM` absolute clock time
- **Distance values** (`total_distance_km`): float rounded to two decimal places
- **Duration values** (`total_time_min`, `service_min`): integer minutes
- Only routes with at least one delivery stop appear in `stops_order.csv` and `summary.csv`
- Stop positions: depot start = 1, delivery stops = 2…n+1, depot end = n+2

## Running the program

```
python3 main.py
```

The program reads from and writes to the current directory. All four input files (`packages.csv`, `vehicles.csv`, `locations.csv`, `distances.csv`) must be present.

## Performance

The algorithm is polynomial in the number of packages and vehicles:
- Construction: O(P × R × N) where P = packages, R = routes, N = avg stops per route
- 2-opt: O(R × N²) per pass
- Or-opt: O(P × R × N) per pass, up to 20 passes

For the maximum specification (500 packages, 50 vehicles, 200 locations, 40 000 distance entries) the solver completes well within practical time limits on the reference hardware.
