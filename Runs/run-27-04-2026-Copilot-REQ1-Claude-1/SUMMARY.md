# Copilot Implementation Summary

## Overview

`copilot` is a single-file Python 3 executable that simulates the onboard
computer of a driver-assistance system.  It is invoked as:

```
copilot --input <dir> --output <dir>
```

## Architecture

### State machine

The system has three states:

| State        | Description                                    |
|-------------|------------------------------------------------|
| `DISENGAGED` | Initial state; only emergency braking is active |
| `ENGAGED`   | All features active; attentiveness timer runs   |
| `ALARM`     | Attentiveness timeout fired; alarm is sounding  |

### Event processing

Rows from `sensor_log.csv` and `driver_events.csv` are merged into a single
stream and sorted by ascending timestamp before processing.  Each event is
dispatched to `process_sensor` or `process_driver_event` on the `Copilot`
object.

### Features

| Feature            | Trigger          | Active in        | Threshold         |
|-------------------|------------------|------------------|-------------------|
| Emergency braking  | Lidar reading    | All modes        | distance < 5 m → BRAKE |
| Lane keeping       | Camera reading   | ENGAGED only     | correction = −offset × 0.5 |
| Cruise control     | Camera reading   | ENGAGED only     | issues throttle command |

### Attentiveness check (ENGAGED mode)

1. 120 s after engagement (or last valid response), a `SteeringWheel /
   small_movement` command is issued.
2. The system waits up to 5 s for a steering-wheel-force driver event.
   - Force ≤ 3 N → valid response; timer resets; system stays ENGAGED.
   - 3 N < force ≤ 10 N → ignored; system continues waiting.
   - No response after 5 s → `Alarm / on` command; transition to `ALARM`.
3. In ALARM, the system waits for a valid response (force ≤ 3 N) to clear
   the alarm (`Alarm / off`) and return to ENGAGED.
4. Force > 10 N at any time causes immediate transition to DISENGAGED.

## Output files

| File                 | Columns                                                    |
|----------------------|------------------------------------------------------------|
| `state_log.csv`      | `timestamp, previous_state, current_state, trigger_event` |
| `commands_log.csv`   | `timestamp, actuator_id, values`                           |
| `feature_decision.csv` | `timestamp, feature, decision`                           |

Only actual state changes are written to `state_log.csv`.

## Design decisions

- **Timestamp parsing**: Supports numeric (float) and ISO-8601 strings;
  timestamps are compared as floats and output verbatim (original string
  from CSV, or the triggering event's timestamp for internally-generated
  records).
- **Event ordering**: Python's stable sort preserves the original file order
  for events with identical timestamps.
- **Attentiveness detection**: Timer checks happen at the start of every
  event handler, providing correct "elapsed-time" semantics in an
  event-driven simulation.
- **Event-type matching**: Driver event types are matched
  case-insensitively; both `engage` / `mode_change` with value `engaged`
  are accepted.
