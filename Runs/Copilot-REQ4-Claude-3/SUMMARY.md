```
python3 -m copilot --input <input_dir> --output <output_dir>
```

## Overview

Copilot is a Python 3 simulation of an onboard ADAS computer.  It reads CSV event logs, runs a formal state machine derived from the Alloy model, and writes structured CSV output files.  No third-party dependencies are required — only the Python standard library.

## Architecture

The code is split into three layers that map directly to the specification's architectural requirement:

| Module | Layer | Responsibility |
|---|---|---|
| `copilot/perception.py` | Perception | Reads `sensor_log.csv` and `driver_events.csv`; yields typed `SensorEvent` / `DriverEvent` objects sorted by timestamp |
| `copilot/decision.py` | Decision | `CopilotStateMachine` — the complete state machine with all Alloy predicates faithfully translated to Python |
| `copilot/actuator.py` | Actuator control | Output record dataclasses (`StateLogEntry`, `CommandEntry`, `FeatureDecisionEntry`) and CSV writers |
| `copilot/__main__.py` | CLI | `argparse`-based entry point, orchestrates the three layers, emits real-time status |

## State Machine

States: `Disengaged`, `Engaged`, `AwaitingResponse`, `Alarming`

| Trigger | From | To |
|---|---|---|
| `ENGAGE` | Disengaged | Engaged |
| `DISENGAGE` | any active | Disengaged |
| `STEERING_FORCE > 10 N` | any active | Disengaged (override FR-04) |
| `STEERING_FORCE ≤ 3 N` | AwaitingResponse | Engaged (attentiveness confirmed) |
| `STEERING_FORCE ≤ 3 N` | Alarming | Engaged (alarm escape) |
| Prompt timeout (120 s) | Engaged | AwaitingResponse |
| Response timeout (5 s) | AwaitingResponse | Alarming |

## Thresholds (from Alloy model)

| Constant | Value |
|---|---|
| `LIDAR_DANGER` | 5.0 m |
| `OVERRIDE_FORCE` | 10.0 N |
| `VALID_RESPONSE_FORCE` | 3.0 N |
| `PROMPT_INTERVAL` | 120.0 s |
| `RESPONSE_WINDOW` | 5.0 s |

## Input / Output Files

**Inputs** (in `<input_dir>`):
- `sensor_log.csv` — columns: `timestamp, sensor_id, sensor_type, data_value, unit`
- `driver_events.csv` — columns: `timestamp, event_type, value`

**Outputs** (written to `<output_dir>`, created if absent):
- `state_log.csv` — columns: `timestamp, previous_state, current_state, trigger_event`
- `commands_log.csv` — columns: `timestamp, actuator_id, values`
- `feature_decision.csv` — columns: `timestamp, feature, decision`

## Example Run

```
python3 -m copilot --input data/run1 --output results/run1
```

Real-time progress is printed to stdout.  Exit code is `0` on success, non-zero if input files are missing or malformed.
