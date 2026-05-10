# FleetRouter — Implementation Summary

## Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point: reads inputs, runs solver, writes outputs |
| `models.py` | Dataclasses: `Location`, `Package`, `Vehicle`, `Route`, `DeliveryStop`, `UndeliverableEntry` |
| `csv_io.py` | CSV reading/writing with HH:MM time parsing and distance formatting |
| `solver.py` | VRPTW solver: pre-filter, greedy construction, 2-opt, or-opt |

## Algorithm

### 1. Individual feasibility pre-filter
Each package is checked against all vehicles for the six reason codes from the Alloy model:
`NO_VEHICLE` → `UNREACHABLE` → `CAPACITY_WEIGHT` → `CAPACITY_VOLUME` → `TIME_WINDOW` → `MAX_DRIVER_TIME`.
Packages failing any check are written directly to `undeliverable.csv`.

### 2. Greedy construction (Solomon I1-style)
Remaining packages are sorted by **priority descending, then `tw_close` ascending** to ensure priority packages are assigned first and tight time windows are handled early.

For each package, the algorithm finds the insertion position (across all routes) that adds the **minimum distance increase** while satisfying all four route constraints: weight capacity, volume capacity, time windows (`arrival ≤ tw_close`, with waiting allowed if `arrival < tw_open`), and driver time (≤ 480 minutes).

### 3. Priority conflict resolution
When a priority=1 package cannot be inserted anywhere due to capacity, the solver tries removing one or two non-priority packages from candidate vehicles to free space. Displaced non-priority packages re-enter the unassigned pool and are retried in a second pass.

### 4. Intra-route 2-opt
For each route, stop-order pairs `(i, j)` are tried as reversals. A reversal is accepted if it reduces route distance and the resulting sequence remains feasible (time windows re-validated after each reversal).

### 5. Inter-route or-opt (3 rounds)
Each round evaluates all single-stop relocations between routes, collects moves that decrease total distance, sorts by savings, and executes the best non-conflicting moves in a single greedy sweep. Capped at 3 rounds to bound runtime.

## Time Model
All times are minutes since 08:00 internally (0 = 08:00, 480 = 16:00). Input/output uses HH:MM format.
Departure from a delivery stop: `max(arrival, tw_open) + service_min`.

## Performance
- 500 packages, 50 vehicles, 200 locations (40,000 distance entries): **~4 seconds** on a modern machine.
- Worst-case construction is O(P × V × K²) where P = packages, V = vehicles, K = average stops per route.

## Output
- `stops_order.csv` — all stops including depot start (position 1) and depot end (last position); only routes with at least one delivery are written.
- `undeliverable.csv` — one row per undeliverable package with reason code; invalid input rows use `INVALID_INPUT`.
- `summary.csv` — per-vehicle totals; only vehicles with deliveries are written.
