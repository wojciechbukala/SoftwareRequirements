```
python3 fleetrouter.py --input <input_dir> --output <output_dir>
```

## FleetRouter — Implementation Summary

### Architecture

The system is a pure-Python package (`fleetrouter/`) with no external dependencies, organised into five modules:

| Module | Responsibility |
|---|---|
| `models.py` | Shared data-classes (`Package`, `Vehicle`, `Location`, `StopResult`), constants (`START_MINUTES=480`, `MAX_DRIVER_MINUTES=480`), and `parse_time`/`format_time` helpers. |
| `reader.py` | Reads and validates all four input CSV files; terminates on missing files; collects warnings for excluded rows. |
| `route.py` | `Route` class: computes schedules (arrival/wait/departure per stop), total distance, total duration, and feasibility. |
| `planner.py` | Assigns packages to vehicles using **cheapest-insertion**: packages sorted by descending priority then ascending `tw_close`; each package is inserted at the position and vehicle that minimises additional distance while satisfying all constraints. |
| `optimizer.py` | **2-opt** (best-improvement, per route) followed by **relocate** (single-package cross-route moves); both phases are repeated until no improvement is found. |
| `writer.py` | Writes the three output CSV files with correct column names, time formats, and rounding. |
| `__main__.py` | CLI (`--input`, `--output`); orchestrates read → assign → optimise → write; prints the final summary line. |

### Algorithm

**Construction (FR-03 / FR-05)**
Priority-1 packages are processed before priority-0 packages (tie-broken by `tw_close`). For each package, every vehicle and every insertion position is evaluated; the position yielding the smallest distance increase (duration as tie-breaker) is accepted only if it passes all four constraints: weight capacity, volume capacity, time-window feasibility, and 8-hour driver-day limit.

**Optimisation (FR-05)**
After construction, 2-opt eliminates route crossings within each vehicle's route. A relocate phase then moves individual packages between routes whenever doing so reduces total fleet distance. The two phases alternate until stable.

**Constraint checking**
`Route.compute_schedule()` walks the stop sequence from the depot (departure 08:00) and returns `None` on the first violation (missing distance entry or late arrival beyond `tw_close`). The caller then inspects edge existence to distinguish `UNREACHABLE` from `TIME_WINDOW`.

### Reason-code precedence

When a package cannot be assigned, the most informative failure reason is reported, ranked by how far into the feasibility check the package progressed:

`NO_VEHICLE` < `UNREACHABLE` < `CAPACITY_WEIGHT` < `CAPACITY_VOLUME` < `TIME_WINDOW` < `MAX_DRIVER_TIME`

### Input / Output files

**Input** (`--input DIR`): `packages.csv`, `vehicles.csv`, `locations.csv`, `distances.csv`

**Output** (`--output DIR`): `stops_order.csv`, `summary.csv`, `undeliverable.csv`

### Requirements coverage

| Requirement | Coverage |
|---|---|
| FR-01 Read input | `reader.read_all` — all four files mandatory; exits on missing file |
| FR-02 Validation | Unknown location IDs excluded; invalid `tw_close ≤ tw_open` → `TIME_WINDOW`; missing distance pairs reported; `UNREACHABLE` applied during assignment |
| FR-03 Assignment | Cheapest-insertion with priority ordering; all four constraint checks; six reason codes |
| FR-04 Routing | Depot-to-depot routes; stop numbering from 1; arrival/wait/departure times per stop |
| FR-05 Optimisation | 2-opt + relocate minimising total distance, duration as tiebreaker |
| FR-06 Output | Three CSV files with specified column names, HH:MM times, km rounded to 2 dp |
