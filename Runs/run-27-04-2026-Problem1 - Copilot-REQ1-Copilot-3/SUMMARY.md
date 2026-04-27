# Copilot Implementation Summary

## What was built

A single-file Python executable `/workspace/copilot` that simulates the onboard computer of a driver-assistance system, matching all requirements in REQUIREMENTS.md.

## Invocation

```
copilot --input <dir> --output <dir>
```

## Architecture

The implementation is a single Python 3 script (~260 lines) with no external dependencies.

### Key classes / functions

| Symbol | Role |
|---|---|
| `CopilotSystem` | Core state machine and output writer |
| `_parse_ts()` | Parses float or ISO-8601 timestamps |
| `_load_sensor_events()` / `_load_driver_events()` | CSV readers |
| `main()` | Merges event streams, drives processing loop |

### Event processing

Both input files are read into a single list and sorted by ascending timestamp (stable sort preserves file order on ties, sensor events before driver events).

### State machine

Two states: `DISENGAGED` (default) and `ENGAGED`.

| Trigger | Transition |
|---|---|
| driver `engage` event | DISENGAGED → ENGAGED |
| driver `disengage` event | ENGAGED → DISENGAGED |
| steering-wheel force > 10 N | ENGAGED → DISENGAGED (any time) |

Only actual state changes are written to `state_log.csv`.

### Feature decisions and actuator commands

| Condition | Feature | Decision | Command |
|---|---|---|---|
| Lidar distance < 5 m (any mode) | emergency braking | BRAKE | BrakingSystem ENGAGE |
| Lidar distance ≥ 5 m (any mode) | emergency braking | NO_BRAKE | — |
| Lidar distance ≥ 5 m + ENGAGED | cruise control | speed adjustment | ThrottleActuator |
| Camera reading + ENGAGED | lane keeping | correction value | SteeringActuator |

Speed adjustment uses a proportional rule: `(distance − 30) × 0.5` m/s (negative = slow down), clamped to 0 beyond 30 m.  
Lane correction: `−offset × 0.5`.

### Attentiveness check

While ENGAGED:
- A `SteeringWheel HAPTIC` command is issued at the first event whose timestamp ≥ `engaged_since + 120 s` (or `last_valid_response + 120 s`).
- The system then waits up to 5 seconds for a `steering_wheel_force` driver event.
  - Force ≤ 3 N within 5 s → valid response; 120 s timer restarted from that moment.
  - Force in (3, 10] N within 5 s → ignored; waiting continues.
  - No valid response within 5 s → `Alarm ON` command issued at first subsequent event.
  - Valid response after alarm → `Alarm OFF` command, timer reset.
  - Force > 10 N → immediate disengagement (any time).

Timing is evaluated in an event-driven fashion: conditions are checked at the timestamp of each arriving event.

## Output files

| File | Description |
|---|---|
| `state_log.csv` | State transitions (only actual changes) |
| `commands_log.csv` | Actuator commands |
| `feature_decision.csv` | Per-feature decisions for every evaluated sensor reading |

All files use comma-separated UTF-8 CSV with a header row.
