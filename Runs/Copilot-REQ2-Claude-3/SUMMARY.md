```
python -m copilot --input <input_dir> --output <output_dir>
```

## Overview

The Copilot driver-assistance simulation is implemented as a Python package (`copilot/`) with clear separation between the perception, decision, and actuator layers as required by the specification.

## Package Structure

| File | Layer | Responsibility |
|------|-------|----------------|
| `copilot/perception.py` | Perception | `SensorEvent` / `DriverEvent` dataclasses; CSV readers; `merge_events()` — merges both streams in ascending timestamp order |
| `copilot/decision.py` | Decision | `FeatureDecision` dataclass; `evaluate_lidar()` (always runs, emergency braking); `evaluate_camera()` (Engaged state only, lane keeping + cruise control) |
| `copilot/actuator.py` | Actuator | `ActuatorCommand` dataclass; factory functions: `brake_command`, `steer_command`, `speed_command`, `prompt_command`, `alarm_command` |
| `copilot/state_machine.py` | Control | `StateMachine` with `check_time_transitions()`, `handle_engage/disengage/steering_force()`; immutable `StateTransition` records |
| `copilot/output.py` | Output | `write_state_log`, `write_commands_log`, `write_feature_decisions` — UTF-8 CSV with header rows |
| `copilot/__main__.py` | Entry point | `argparse` CLI; event loop (PF-02); real-time stdout progress; wires all layers together |

## Functional Requirements Coverage

- **FR-01** — Four states (Disengaged, Engaged, AwaitingResponse, Alarming); starts Disengaged; only actual state changes written to `state_log.csv`.
- **FR-02** — Emergency braking (Lidar < 5 m) always evaluated first regardless of mode; camera events produce lane-keeping and cruise-control decisions only when Engaged; Disengaged mode produces no feature decisions or actuator commands for camera events.
- **FR-03** — 120 s attentiveness prompt issues `SteeringWheel/small_movement` command and transitions to AwaitingResponse; ≤ 3 N response → back to Engaged; 3–10 N → ignored; 5 s timeout → Alarming with `Alarm/continuous_alarm` command; ≤ 3 N in Alarming → Engaged.
- **FR-04** — Steering force > 10 N immediately transitions to Disengaged from any state.
- **FR-05** — Reads `sensor_log.csv` and `driver_events.csv`; merges and processes in ascending timestamp order.

## Key Design Decisions

- **Event-driven timers**: time-based transitions (120 s prompt, 5 s response window) are checked at the timestamp of each incoming event. This is the correct model for an event-driven simulation — no real-time clock is used.
- **Emergency braking priority**: Lidar evaluation runs before any other feature and returns early if braking is triggered, preventing camera processing in the same cycle (PF-01).
- **Pending commands queue**: `StateMachine.pending_commands` decouples time-triggered command emission from the actuator layer; the event loop drains this list after each transition check.
- All output CSVs use UTF-8 encoding, comma separator, and a required header row.

## Input / Output File Formats

**Inputs** (in `<input_dir>`):
- `sensor_log.csv` — `timestamp, sensor_id, sensor_type, data_value, unit`
- `driver_events.csv` — `timestamp, event_type, value`

**Outputs** (in `<output_dir>`):
- `state_log.csv` — `timestamp, previous_state, current_state, trigger_event`
- `commands_log.csv` — `timestamp, actuator_id, values`
- `feature_decision.csv` — `timestamp, feature, decision`
