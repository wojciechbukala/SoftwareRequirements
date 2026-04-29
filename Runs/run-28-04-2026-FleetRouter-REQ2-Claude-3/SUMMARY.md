# FleetRouter — Implementation Summary

## What Was Built

A command-line daily route-planning tool for courier companies, implemented in Python with no external dependencies.

## File Structure

```
fleetrouter       Shell script entry point (chmod +x)
main.py           CLI argument parsing and orchestration
models.py         Data classes: Package, Vehicle, Location, Stop, Route
reader.py         CSV ingestion and validation (FR-01, FR-02)
planner.py        Assignment, route construction, and optimisation (FR-03–FR-05)
writer.py         Output file generation (FR-06)
```

## Invocation

```
./fleetrouter --input <input_dir> --output <output_dir>
```

Both arguments are mandatory. The program reads four CSV files from `<input_dir>` and writes three CSV files to `<output_dir>`.

## Algorithm

### Input Validation (`reader.py`)
- Missing files trigger an immediate error and non-zero exit.
- Packages referencing unknown locations or with invalid priority values (not 0 or 1) are excluded and reported to stderr.
- Packages with `tw_close <= tw_open` are immediately written to `undeliverable.csv` with reason `TIME_WINDOW`.

### Package Assignment (`planner.py` → `_assign_packages`)
1. Packages are sorted: priority-1 packages first, then by `tw_open` ascending.
2. For each package, every vehicle is tried using **cheapest insertion**: the position in the vehicle's current route that minimises the added distance is selected.
3. Before trying positions, cumulative weight and volume are checked (returns `CAPACITY_WEIGHT` / `CAPACITY_VOLUME` early).
4. For each candidate insertion, `simulate_route` is called to verify time windows and the 8-hour driver limit.
5. The vehicle offering the lowest extra distance is chosen; on failure across all vehicles the most informative reason is reported (see Failure Level below).

### Route Simulation (`simulate_route`)
For each stop in order, the function computes:
- **arrival** = previous departure + travel time
- **waiting** = max(0, tw_open − arrival)
- **departure** = arrival + waiting + service_min
- Fails with `TIME_WINDOW` if arrival > tw_close, `UNREACHABLE` if a required distance entry is absent, `MAX_DRIVER_TIME` if total duration exceeds 480 minutes.

All vehicles depart their depot at **08:00** (DA-04).

### Failure Reason Selection
When a package cannot be assigned to any vehicle, the reason reported is the one from the vehicle that made it furthest through the constraint checks (most specific failure):

| Level | Reason          | Description                          |
|-------|-----------------|--------------------------------------|
| 5     | MAX_DRIVER_TIME | Route would exceed 8-hour limit      |
| 4     | TIME_WINDOW     | Delivery window cannot be met        |
| 3     | UNREACHABLE     | Required distance entry missing      |
| 2     | CAPACITY_VOLUME | Volume capacity exceeded             |
| 1     | CAPACITY_WEIGHT | Weight capacity exceeded             |
| 0     | NO_VEHICLE      | Fallback (no vehicle available)      |

### Route Optimisation (`_two_opt`)
After assignment, each vehicle's route is improved with **2-opt**: all pairs of edges are tested; if reversing the segment between them yields a feasible route with lower total distance, the swap is accepted. The process repeats until no improving swap exists.

Primary objective: minimise total fleet distance. Secondary: minimise total fleet duration (the 2-opt objective is distance, which inherently serves the primary goal; duration differences are reflected in `simulate_route`).

## Output Files

| File               | Contents                                                    |
|--------------------|-------------------------------------------------------------|
| `stops_order.csv`  | One row per stop: route_id, vehicle_id, position, location, package, arrival, departure |
| `summary.csv`      | One row per vehicle (including idle ones): distance, time, packages delivered |
| `undeliverable.csv`| One row per unassigned package with exactly one reason code |

Time values are formatted as `HH:MM`. Distances are rounded to two decimal places.

## Design Decisions

- **Pure Python, no third-party libraries** — satisfies the offline/single-machine constraint (L-01–L-03).
- **Greedy cheapest insertion + 2-opt** — practical VRPTW heuristic; runs well within the stated performance envelope (500 packages, 50 vehicles, 200 locations).
- **Same-location distance** — when `from_location_id == to_location_id`, distance and travel time are treated as 0 to handle packages at a depot without requiring a self-loop in `distances.csv`.
- **Undeliverable reason priority** — selects the most informative failure so operators can act on the output.
