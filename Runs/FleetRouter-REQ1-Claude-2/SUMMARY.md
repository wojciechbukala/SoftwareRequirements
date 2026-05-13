```
PATH="/workspace/bin:$PATH" fleetrouter --input <input_dir> --output <output_dir>
```

## Implementation

FleetRouter is a Python package (`fleetrouter/`) with a command-line entry point at `/workspace/bin/fleetrouter`.

### Structure

- `fleetrouter/__main__.py` — all logic: input parsing, validation, routing, output
- `fleetrouter/__init__.py` — package marker
- `pyproject.toml` — package metadata and script entry point
- `bin/fleetrouter` — executable wrapper (adds `/workspace` to `sys.path`)

### Algorithm

**Input validation (pre-filter):**
- Vehicles referencing unknown `depot_location_id` are silently excluded from processing
- Packages referencing unknown `destination_id` → `undeliverable.csv` with `UNREACHABLE`
- Packages with invalid time windows (`tw_open >= tw_close`) → `undeliverable.csv` with `TIME_WINDOW`
- Packages whose destination has no bidirectional path from any valid depot → `undeliverable.csv` with `UNREACHABLE`

**Assignment (cheapest insertion heuristic):**
1. Packages are sorted by descending priority (1 before 0), then by earliest `tw_close` (most urgent first)
2. For each package, every vehicle is evaluated at every possible insertion position
3. The vehicle+position minimizing total route distance (then duration as tiebreaker) is chosen
4. Vehicles with insufficient remaining weight/volume capacity are skipped
5. `simulate_route` checks time windows and the 8-hour driver limit for each candidate insertion

**Rejection reason determination (in priority order):**
1. `CAPACITY_WEIGHT` — no vehicle has sufficient remaining weight capacity
2. `CAPACITY_VOLUME` — no vehicle (with sufficient weight) has sufficient volume capacity
3. `UNREACHABLE` — routing simulation failed due to missing distance entry
4. `TIME_WINDOW` — package cannot be delivered within its time window
5. `MAX_DRIVER_TIME` — delivery would exceed the 8-hour driver limit
6. `NO_VEHICLE` — catch-all

**Route optimization:**
- After all assignments, each vehicle's route is improved with 2-opt local search
- 2-opt swaps are accepted only if they reduce total distance (or reduce duration at equal distance) without violating any constraints

**Route simulation:**
- Vehicle departs depot at 08:00
- Travel times from `distances.csv` are used; missing entries raise `UNREACHABLE`
- If vehicle arrives before `tw_open`, it waits; if `service_start > tw_close`, route is infeasible
- Total time includes return trip to depot; must not exceed 480 minutes

### Output

- `stops_order.csv` — one row per delivery stop (arrival/departure in HH:MM)
- `undeliverable.csv` — one row per undeliverable package with exactly one reason code
- `summary.csv` — per-vehicle totals (distance rounded to 2 decimal places, duration as integer minutes)
