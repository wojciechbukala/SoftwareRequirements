```
fleetrouter --input <input_dir> --output <output_dir>
```

## Installation

```
pip install -e /workspace/ --target=/workspace/.pkgs --break-system-packages
```

Or run directly:

```
python3 /workspace/fleetrouter.py --input <input_dir> --output <output_dir>
```

Or make the wrapper executable and add to PATH:

```
chmod +x /workspace/fleetrouter
export PATH=/workspace:$PATH
fleetrouter --input <input_dir> --output <output_dir>
```

## What was implemented

**FleetRouter** (`fleetrouter.py`) is a single-file Python 3 implementation of a vehicle routing planner for a courier company. It reads four CSV input files and produces three CSV output files.

### Input validation

- **Unknown locations**: packages or vehicles referencing a `location_id` not in `locations.csv` are excluded; packages are recorded as `UNREACHABLE`.
- **Invalid time windows**: packages where `tw_open >= tw_close` (or unparseable times) are recorded as `TIME_WINDOW`.
- **Missing distance entries**: packages whose destination cannot be reached from any depot (or returned from) are recorded as `UNREACHABLE`.

### Route planning algorithm

1. **Sorting**: priority=1 packages are sorted before priority=0; within the same priority, packages are ordered by `tw_open` (earliest first).
2. **Greedy cheapest insertion**: for each package in sorted order, every vehicle is evaluated. The algorithm tries every insertion position in the vehicle's current route and picks the position + vehicle combination that adds the least distance while remaining fully feasible (capacity, time window, 8-hour driver limit).
3. **2-opt improvement**: after all packages are assigned, each vehicle's route is improved using 2-opt swaps — reversing sub-sequences to reduce total distance while keeping all constraints satisfied.

### Rejection reason logic

When no vehicle can accept a package, exactly one reason is assigned:
- `CAPACITY_WEIGHT` — no vehicle has sufficient remaining weight capacity
- `CAPACITY_VOLUME` — vehicles that pass weight all fail volume
- `TIME_WINDOW` — capacity-feasible insertions fail because arrival exceeds `tw_close`
- `MAX_DRIVER_TIME` — capacity-feasible insertions push total route duration past 8 hours
- `NO_VEHICLE` — none of the above explicitly apply

### Output

- **stops_order.csv**: ordered stops per vehicle route with arrival/departure times in HH:MM
- **undeliverable.csv**: packages that could not be delivered with their reason code
- **summary.csv**: per-vehicle totals for distance (rounded to 2 decimal places), duration (integer minutes), and delivered package count

### Setup files

- `fleetrouter.py` — main implementation module
- `fleetrouter` — executable entry-point script (requires `/workspace` in PATH or invoke directly)
- `setup.py` — pip-installable package definition with `fleetrouter` console script entry point
