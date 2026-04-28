# Copilot ADAS Simulation – Implementation Summary

## What was built

A Python implementation of the Copilot onboard-computer simulation described in `REQUIREMENTS.md`.  The system faithfully translates the Alloy formal model into executable code, processes CSV input event streams, and produces three CSV output reports.

---

## Directory structure

```
copilot/                 # Python package (the implementation)
    __init__.py          # Package docstring / architecture overview
    models.py            # Enums, threshold constants, data classes
    perception.py        # Input layer: CSV parsing → typed event objects
    decision.py          # Decision layer: core state-machine engine
    output.py            # Output layer: typed results → CSV files
    __main__.py          # CLI entry point (python -m copilot …)
copilot.py              # Thin top-level wrapper (./copilot.py …)
tests/
    __init__.py
    test_engine.py       # 27 unit tests covering all Alloy scenarios/assertions
REQUIREMENTS.md          # Original specification
SUMMARY.md               # This file
```

---

## How to run

```bash
# Using the module directly (cross-platform):
python3 -m copilot --input <input_dir> --output <output_dir>

# Or via the wrapper script:
./copilot.py --input <input_dir> --output <output_dir>
```

Both `--input` and `--output` are mandatory.

### Input files (placed in `<input_dir>`)

| File | Columns |
|------|---------|
| `sensor_log.csv` | `timestamp, sensor_id, sensor_type, data_value, unit` |
| `driver_events.csv` | `timestamp, event_type, value` |

`sensor_type` must be `Lidar` or `Camera`.  
`event_type` must be `ENGAGE`, `DISENGAGE`, or `STEERING_FORCE`.

### Output files (written to `<output_dir>`)

| File | Columns |
|------|---------|
| `state_log.csv` | `timestamp, previous_state, current_state, trigger_event` |
| `commands_log.csv` | `timestamp, actuator_id, values` |
| `feature_decision.csv` | `timestamp, feature, decision` |

---

## Architecture

The implementation follows the three-layer separation required by §3.2:

### Perception layer (`perception.py`)
Reads and validates both CSV input files, converts rows into typed `SensorEvent` / `DriverEvent` objects, merges them, and sorts by timestamp.

### Decision layer (`decision.py`)
`CopilotEngine` is a direct translation of the Alloy predicates:

| Alloy predicate | Python method |
|-----------------|---------------|
| `handleEngageDriverEvent` | `_handle_engage` |
| `handleDisengageDriverEvent` | `_handle_disengage` |
| `handleSteeringForceDriverEvent` | `_handle_steering_force` |
| `handleLidarSensorEvent` | `_handle_lidar` |
| `handleCameraSensorEvent` | `_handle_camera` |
| `internalStep` | `_process_internal_steps` |

Between consecutive events the engine runs `_process_internal_steps(up_to_time)` which applies time-based transitions in the gap:
1. `Engaged` + elapsed ≥ `PROMPT_INTERVAL` (120) → `AwaitingResponse` + SteeringMotor haptic command
2. `AwaitingResponse` + elapsed ≥ `RESPONSE_WINDOW` (5) → `Alarming` + AlarmActuator command
3. `Alarming` → one `AlarmActuator` command emitted per time unit until the next external event

### Output layer (`output.py`)
Iterates over the three in-memory log lists produced by the engine and writes them to CSV files with the required headers.

---

## Threshold constants (from Alloy model)

| Constant | Value | Meaning |
|----------|-------|---------|
| `LIDAR_DANGER` | 5 | Obstacle distance below which emergency braking activates |
| `OVERRIDE_FORCE` | 10 | Steering force above which manual override is triggered |
| `VALID_RESPONSE_FORCE` | 3 | Maximum force accepted as a valid driver attentiveness response |
| `PROMPT_INTERVAL` | 120 | Time units between attentiveness prompts |
| `RESPONSE_WINDOW` | 5 | Time units the driver has to respond before the alarm escalates |

---

## State machine

```
Disengaged  ──ENGAGE──►  Engaged  ──PROMPT_TIMEOUT──►  AwaitingResponse
     ▲                      │                                  │
     │◄───DISENGAGE──────────┤                  RESPONSE_TIMEOUT▼
     │◄───OVERRIDE───────────┤            Alarming ◄────────────┘
     │◄───OVERRIDE───────────┘                  │
     │◄──────────────────────────────DISENGAGE──┘
     │◄──────────────────────────────OVERRIDE───┘
     │                         ▲
     └──────────────STEERING_FORCE(≤3)─────────┘   (alarm escape)
```

---

## Test suite

Run with the standard library:

```bash
python3 -m unittest tests.test_engine -v
```

27 tests covering:
- Engage / Disengage transitions
- Emergency braking (Lidar, both thresholds)
- Lane keeping / cruise control (Camera, state conditions)
- Manual override from all states
- Attentiveness prompt timing and haptic command emission
- Response timeout → Alarming escalation
- Alarm escape via low steering force
- All four Alloy assertions (`OverrideAlwaysDisengages`, `BrakeDecisionImpliesBrakeCommand`, `AlarmingPrecededByAwaiting`, `DisengagedHasNoLaneKeepingDecisions`)
- Edge cases and integration scenarios

All 27 tests pass.

---

## Design notes

- **No third-party dependencies** – the entire implementation uses only the Python standard library (`csv`, `argparse`, `dataclasses`, `enum`).  
- **Portability** – runs on any POSIX system or Windows with Python 3.10+.  
- **Performance** – processing is O(n) in the number of events; the 0.8 ms wall time observed for a 7-event sample is well within the 50 ms per-event requirement.  
- **Clean architecture** – each layer (`perception`, `decision`, `output`) has a single responsibility and no I/O in the decision engine, making unit testing straightforward without mocking.
