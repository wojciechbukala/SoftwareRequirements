```
python3 /workspace/fleetrouter --input <input_dir> --output <output_dir>
```

## Implementation

Single-file Python script `/workspace/fleetrouter` (executable) implementing the full FleetRouter specification.

### Architecture

**Data model**: `Package`, `Vehicle`, and `VehicleRoute` dataclasses. `VehicleRoute` holds the ordered package list and computes timing/distance on demand.

**Input validation** (in order):
1. Vehicles with unknown `depot_location_id` are silently excluded.
2. Packages with unknown `destination_id` → `UNREACHABLE`.
3. Packages with invalid time windows (`tw_open >= tw_close`) → `TIME_WINDOW`.
4. Packages whose destination is unreachable from every vehicle depot (missing distance entry in either direction) → `UNREACHABLE`.

**Assignment algorithm** — cheapest-insertion heuristic for VRPTW:
- Packages are sorted priority-descending (1 before 0), then by `package_id` for stability.
- For each package, every possible insertion position in every vehicle route is evaluated.
- The insertion is chosen that minimises added distance first, then total route duration (ties broken by duration).
- If no vehicle can accept the package, the failure reason is determined by checking capacity universally (`CAPACITY_WEIGHT` / `CAPACITY_VOLUME`), then examining routing failures (`TIME_WINDOW`, `MAX_DRIVER_TIME`, `UNREACHABLE`, `NO_VEHICLE`) among capacity-capable vehicles.

**Route timing**: Each route starts at 08:00. Vehicles wait at stops if they arrive before `tw_open`. Driver total time (depot departure to depot return) is capped at 480 minutes.

**Outputs**:
- `stops_order.csv` — one row per delivery stop with `route_id`, `vehicle_id`, position, location, package, arrival/departure times (HH:MM).
- `undeliverable.csv` — each undeliverable package with exactly one reason code.
- `summary.csv` — per-vehicle totals: distance (2 d.p.), duration (integer minutes), package count. Vehicles with zero deliveries are included with zeros.

### Reason code priority (undeliverable)
`CAPACITY_WEIGHT` → `CAPACITY_VOLUME` → `TIME_WINDOW` → `MAX_DRIVER_TIME` → `UNREACHABLE` → `NO_VEHICLE`
