```
python3 -m copilot --input <input_dir> --output <output_dir>
```

## Overview

Copilot is implemented as a Python 3 package (`copilot/`) with no third-party dependencies. The architecture follows the three-layer separation mandated by the requirements: **perception → decision → actuator**.

## Package Structure

| File | Role |
|---|---|
| `copilot/models.py` | Typed dataclasses for all domain objects (`State`, `SensorEvent`, `DriverEvent`, `StateLogEntry`, `CommandEntry`, `FeatureDecisionEntry`) |
| `copilot/perception.py` | Perception layer — parses `sensor_log.csv` into `SensorEvent` objects |
| `copilot/decision.py` | Decision layer — maps sensor readings to ADAS feature decisions (`EmergencyBraking`, `LaneKeeping`, `CruiseControl`) |
| `copilot/actuator.py` | Actuator layer — translates decisions into typed `CommandEntry` objects for `BrakingSystem`, `SteeringMotor`, `SpeedActuator`, `AlarmActuator` |
| `copilot/simulation.py` | State-machine engine; processes events in timestamp order with time-based internal transitions |
| `copilot/io_utils.py` | CSV I/O: loads `driver_events.csv`, writes the three output files |
| `copilot/cli.py` | CLI argument parsing (`--input`, `--output`) and real-time status output |
| `copilot/__main__.py` | Enables `python3 -m copilot` invocation |

## State Machine (mirrors Alloy model exactly)

**States**: `Disengaged` → `Engaged` → `AwaitingResponse` → `Alarming`

**Threshold constants** (from the Alloy `fun` declarations):

| Constant | Value |
|---|---|
| `LIDAR_DANGER_THRESHOLD` | 5.0 m |
| `OVERRIDE_FORCE` | 10.0 N |
| `VALID_RESPONSE_FORCE` | 3.0 N |
| `PROMPT_INTERVAL` | 120.0 s |
| `RESPONSE_WINDOW` | 5.0 s |

**Event handlers**:
- `ENGAGE`: `Disengaged → Engaged` (no-op otherwise); resets the prompt countdown.
- `DISENGAGE`: any non-`Disengaged` → `Disengaged`.
- `STEERING_FORCE`:
  - force > 10 N → `Disengaged` (FR-04 override).
  - force ≤ 3 N while `AwaitingResponse` or `Alarming` → `Engaged` (valid response / alarm escape).
  - mid-range force while `AwaitingResponse` → no-op.
- **Lidar**: emits `EmergencyBraking = BRAKE` + `BrakingSystem` command when distance < 5 m; `NO_BRAKE` otherwise. State-independent.
- **Camera**: emits `LaneKeeping = ADJUST`, `CruiseControl = ADJUST`, `SteeringMotor ADJUST`, `SpeedActuator ADJUST` — only when `Engaged`.

**Internal (time-based) transitions** fire between external events:
1. `Engaged` for ≥ 120 s since `lastPrompt` → `AwaitingResponse` + `SteeringMotor PROMPT` at the exact computed time.
2. `AwaitingResponse` for ≥ 5 s since `awaitingSince` → `Alarming` + `AlarmActuator ALARM` at the exact computed time.
3. While `Alarming`, one `AlarmActuator ALARM` command is emitted at the timestamp of each subsequent external event (models the continuous alarm tick).

## Input / Output Files

**Inputs** (place in `--input` directory):
- `sensor_log.csv`: `timestamp, sensor_id, sensor_type, data_value, unit`
- `driver_events.csv`: `timestamp, event_type, value`

**Outputs** (written to `--output` directory):
- `state_log.csv`: `timestamp, previous_state, current_state, trigger_event`
- `commands_log.csv`: `timestamp, actuator_id, values`
- `feature_decision.csv`: `timestamp, feature, decision`

## Design Decisions

- **Pure stdlib**: `csv`, `argparse`, `pathlib`, `time`, `enum`, `dataclasses` — no pip install required.
- **Portable**: `pathlib` handles both POSIX and Windows path separators. UTF-8 encoding is explicit on every file open.
- **Performance**: sorting N events is O(N log N); each event handler is O(1). Well within the 50 ms per-event budget on any modern hardware.
- **Internal transition timing**: computed transition times use floating-point arithmetic matching the input timestamps; strict less-than (`<`) is used so that an external event at exactly the threshold time is processed before the internal transition fires (consistent with the Alloy model's priority of `step[e]` over `internalStep`).
