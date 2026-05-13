```
python3 main.py
```

## Overview

FleetRouter is a Python-based Vehicle Routing Problem with Time Windows (VRPTW) solver for daily courier logistics planning.

## Files

- `main.py` — entry point: reads CSVs, invokes solver, writes output files
- `models.py` — data classes: `Package`, `Vehicle`, `Location`, `DistanceMatrix`
- `solver.py` — VRPTW solver with greedy insertion + 2-opt + or-opt local search

## Algorithm

**Constructive phase** — Greedy cheapest insertion:
- Packages sorted by priority DESC, then `tw_close` ASC (deadline-first within same priority)
- For each package, find the (vehicle, position) pair with minimum additional distance that satisfies all constraints
- Priority packages are processed first, ensuring they claim capacity before non-priority ones

**Local search** — Two-phase improvement:
1. **2-opt within routes**: reverses sub-sequences to reduce route distance, up to 50 passes per route
2. **Or-opt between routes**: relocates single packages to cheaper positions in other vehicles' routes, up to 3 full passes

## Constraints enforced

- Weight and volume capacity per vehicle
- Time windows: arrive at or before `tw_close`; wait until `tw_open` if early
- Driver time: return to depot within 480 minutes of 08:00 departure
- Route reachability: both outbound and inbound paths must exist in `distances.csv`

## Undeliverable reason codes

Checked individually before assignment:
- `NO_VEHICLE` — no vehicles exist, or no vehicle can accommodate the package given current assignments
- `UNREACHABLE` — no round-trip path exists from any depot to the destination
- `CAPACITY_WEIGHT` — weight exceeds all vehicles' capacity
- `CAPACITY_VOLUME` — volume exceeds all vehicles' capacity
- `MAX_DRIVER_TIME` — outbound + service + inbound > 480 min for all vehicles
- `TIME_WINDOW` — earliest possible arrival > `tw_close` for all vehicles

## Input validation

Invalid rows (bad types, missing fields, `priority` outside {0,1}, `tw_close <= tw_open`, unknown location IDs) are logged to stderr and skipped.

## Performance

Tested at maximum scale (500 packages, 50 vehicles, 200 locations, 40 000 distance entries): completes in under 3 seconds on a modern machine.
