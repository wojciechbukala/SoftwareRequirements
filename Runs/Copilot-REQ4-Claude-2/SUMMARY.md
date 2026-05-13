```
python3 copilot.py --input <input_dir> --output <output_dir>
```

## Implementation Overview

The Copilot ADAS simulation is implemented in Python 3 across four modules that mirror the three-layer architecture required by the specification.

### Modules

| File | Layer | Responsibility |
|------|-------|----------------|
| `perception.py` | Perception | Parses `sensor_log.csv` and `driver_events.csv` into typed Python dataclasses (`SensorEvent`, `DriverEvent`). |
| `decision.py` | Decision | Implements the state machine: `Disengaged → Engaged → AwaitingResponse → Alarming` and back. Processes all events in chronological order and simulates time-based internal ticks at integer-second marks between events. |
| `actuator.py` | Actuator Control | Writes the three output CSV files (`state_log.csv`, `commands_log.csv`, `feature_decision.csv`) from the engine's accumulated records. |
| `copilot.py` | CLI Entry Point | Parses `--input`/`--output` arguments, wires the three layers together, and prints real-time status to stdout. |

### State Machine (decision.py)

**Constants** (direct mapping from Alloy model):
- `LIDAR_DANGER = 5.0` — obstacle distance threshold for emergency braking
- `OVERRIDE_FORCE = 10.0 N` — steering force that triggers manual override → Disengaged
- `VALID_RESPONSE_FORCE = 3.0 N` — maximum force counted as a valid attentiveness response
- `PROMPT_INTERVAL = 120.0 s` — gap between attentiveness checks
- `RESPONSE_WINDOW = 5.0 s` — driver response window before alarm escalates

**Event handling:**

| Event | Guard | Action |
|-------|-------|--------|
| ENGAGE | state = Disengaged | → Engaged; reset `last_prompt` |
| DISENGAGE | state ≠ Disengaged | → Disengaged |
| STEERING_FORCE > 10 N | any | → Disengaged (override) |
| STEERING_FORCE ≤ 3 N | AwaitingResponse or Alarming | → Engaged; reset `last_prompt` |
| STEERING_FORCE 3–10 N | AwaitingResponse | no-op (insufficient response) |
| Lidar (value < 5) | any | EmergencyBraking=BRAKE + BrakingSystem command |
| Lidar (value ≥ 5) | any | EmergencyBraking=NO_BRAKE |
| Camera | Engaged | LaneKeeping=ADJUST, CruiseControl=ADJUST + SteeringMotor + SpeedActuator commands |

**Internal (time-driven) steps** are simulated at each integer-second mark between consecutive events, enforcing that no internal tick fires at the exact timestamp of an external event (events take priority):
- `Engaged` and `currentTime ≥ last_prompt + 120` → AwaitingResponse + SteeringMotor prompt command
- `AwaitingResponse` and `currentTime ≥ awaiting_since + 5` → Alarming + AlarmActuator command
- `Alarming` → AlarmActuator command (one per tick, continuous)

After the final event, if the system is in Alarming or AwaitingResponse, ticks continue for one additional `RESPONSE_WINDOW` period so the output reflects the system's live alarm state.

### Output Columns

- **state_log.csv**: `timestamp, previous_state, current_state, trigger_event`  
  `trigger_event` is `ENGAGE`, `DISENGAGE`, `STEERING_FORCE` for driver events; `PROMPT_CHECK` or `RESPONSE_TIMEOUT` for internal transitions.
- **commands_log.csv**: `timestamp, actuator_id, values`  
  Actuator IDs: `BrakingSystem`, `SteeringMotor`, `SpeedActuator`, `AlarmActuator`.
- **feature_decision.csv**: `timestamp, feature, decision`  
  Features: `EmergencyBraking` (BRAKE / NO_BRAKE), `LaneKeeping` (ADJUST), `CruiseControl` (ADJUST).

### Design Decisions

- **Float timestamps throughout** — event timestamps from CSVs are kept as floats; the Alloy integer-time model is faithfully replicated by simulating internal ticks at integer-second marks.
- **Exclusive-of-event timing** — when simulating internal steps between events, the tick at exactly `to_time` is excluded when `to_time` is an integer (an external event fires at that instant instead).
- **No third-party dependencies** — uses only Python standard library (`csv`, `argparse`, `math`, `os`, `sys`, `time`), satisfying the portability requirement for any POSIX or Windows system with Python 3.
- **50 ms latency** — processing is in-memory; benchmarked at sub-millisecond on a modern laptop for typical event streams.
