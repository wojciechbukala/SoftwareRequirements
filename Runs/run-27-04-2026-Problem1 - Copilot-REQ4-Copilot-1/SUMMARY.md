# Copilot ADAS Simulation — Implementation Summary

## Overview

A Python implementation of the Copilot Advanced Driver Assistance System simulator, derived directly from the Alloy6 formal model in `REQUIREMENTS.md`.  The system reads CSV event logs, runs a discrete-time state machine, and writes decision/command/state-transition outputs to CSV files.

---

## Repository layout

```
copilot/
├── main.py          # Entry point
├── cli.py           # --input / --output argument parsing
├── models.py        # Domain types (enums + dataclasses)
├── perception.py    # CSV input parsing (perception layer)
├── decision.py      # State machine logic (decision layer)
├── actuator.py      # CSV output writing (actuator layer)
├── engine.py        # Orchestration + real-time status output
└── tests/
    ├── test_decision.py    # 37 unit tests for state-machine logic
    ├── test_perception.py  # 7 unit tests for CSV parsing
    ├── test_actuator.py    # 4 unit tests for CSV writing
    └── data/
        └── input/          # Sample input files for smoke-testing
```

---

## Usage

```bash
python3 copilot/main.py --input <input_dir> --output <output_dir>
```

**Input files** (in `<input_dir>`):
| File | Columns |
|---|---|
| `sensor_log.csv` | `timestamp, sensor_id, sensor_type, data_value, unit` |
| `driver_events.csv` | `timestamp, event_type, value` |

**Output files** (written to `<output_dir>`):
| File | Columns |
|---|---|
| `state_log.csv` | `timestamp, previous_state, current_state, trigger_event` |
| `commands_log.csv` | `timestamp, actuator_id, values` |
| `feature_decision.csv` | `timestamp, feature, decision` |

---

## Architecture

The code follows a strict three-layer separation as required by §3.2:

### Perception layer (`perception.py`)
Reads `sensor_log.csv` and `driver_events.csv`, parses each row into typed dataclass instances (`SensorEvent`, `DriverEvent`), and returns a single time-sorted list of all input events.

### Decision layer (`decision.py`)
`CopilotStateMachine` implements the four-state FSM (`Disengaged → Engaged → AwaitingResponse → Alarming`) from the Alloy model.

Time is simulated tick-by-tick between consecutive events.  For every integer second strictly between the last processed timestamp and the next event's timestamp, `_internal_tick(t)` fires and may trigger:

| Condition | Transition | Output |
|---|---|---|
| `Engaged` for ≥ 120 s since last prompt | → `AwaitingResponse` | `SteeringMotor PROMPT` |
| `AwaitingResponse` for ≥ 5 s | → `Alarming` | `AlarmActuator ALARM` |
| `Alarming` (each tick) | stay `Alarming` | `AlarmActuator ALARM` |

Event handlers:

| Event | Condition | Transition |
|---|---|---|
| `ENGAGE` | state = `Disengaged` | → `Engaged` |
| `DISENGAGE` | state ≠ `Disengaged` | → `Disengaged` |
| `STEERING_FORCE` (force > 10 N) | any | → `Disengaged` (override) |
| `STEERING_FORCE` (force ≤ 3 N) | `AwaitingResponse` | → `Engaged` (valid response) |
| `STEERING_FORCE` (force ≤ 3 N) | `Alarming` | → `Engaged` (alarm escape) |
| `Lidar` (value < 5) | any | emit `EmergencyBraking=BRAKE` + `BrakingSystem` command |
| `Lidar` (value ≥ 5) | any | emit `EmergencyBraking=NO_BRAKE` |
| `Camera` | `Engaged` | emit `LaneKeeping=ADJUST`, `CruiseControl=ADJUST`, `SteeringMotor`, `SpeedActuator` |

### Actuator layer (`actuator.py`)
Writes the three output CSV files from the in-memory lists accumulated by the decision layer.

### Engine (`engine.py`)
Wires the three layers together and prints real-time status to stdout for every event processed.

---

## Threshold constants (from Alloy model)

| Name | Value | Meaning |
|---|---|---|
| `LIDAR_DANGER` | 5 | Obstacle data_value below this triggers braking |
| `OVERRIDE_FORCE` | 10 N | Steering force above this immediately disengages |
| `VALID_RESPONSE_FORCE` | 3 N | Steering force at/below this is a valid attentiveness reply |
| `PROMPT_INTERVAL` | 120 s | Gap between attentiveness prompts while Engaged |
| `RESPONSE_WINDOW` | 5 s | Time the driver has to respond before alarm fires |

---

## Tests

45 unit tests cover all functional requirements and the four Alloy assertions:

- `OverrideAlwaysDisengages`
- `BrakeDecisionImpliesBrakeCommand`
- `AlarmingPrecededByAwaiting`
- `DisengagedHasNoLaneKeepingDecisions`

Run with:
```bash
# If pytest is available
python3 -m pytest copilot/tests/ -v

# Standard library only
python3 -m unittest discover copilot/tests/
```

---

## Design decisions

- **Standard library only** — no third-party runtime dependencies; runs on any Python 3.7+ environment (POSIX or Windows).
- **Integer timestamps** — event timestamps from the CSV are treated as integer seconds, matching the Alloy model's discrete-tick semantics.
- **Tick-by-tick simulation between events** — ensures internal transitions (attentiveness prompt, response timeout, continuous alarm) fire at the precise second dictated by the threshold constants.
- **No hardcoded paths** — all file paths are supplied via `--input` / `--output` CLI arguments.
