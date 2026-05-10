```
python3 -m copilot --input <input_dir> --output <output_dir>
```

## Implementation Overview

The Copilot driver-assistance simulation is implemented as a Python package (`copilot/`) with a clear three-layer separation as required by the design constraints.

### Architecture

| Module | Layer | Responsibility |
|---|---|---|
| `ingestion.py` | Perception | Reads `sensor_log.csv` and `driver_events.csv`, merges into a single timestamp-sorted event stream |
| `perception.py` | Perception | Interprets raw sensor readings into structured `LidarObservation` and `CameraObservation` objects |
| `decision.py` | Decision | Evaluates autonomous feature outcomes (emergency braking, lane keeping, cruise control) from observations |
| `actuator.py` | Actuator Control | Constructs typed `ActuatorCommand` objects for each physical actuator |
| `state_machine.py` | Orchestration | Maintains runtime context, drives state transitions, dispatches events through all layers |
| `writer.py` | Output | Flushes accumulated records to the three output CSV files |
| `__main__.py` | CLI | Argument parsing, top-level coordination, real-time status output |
| `models.py` | Shared | Dataclasses and enums shared across all layers |

### Functional Requirements Coverage

- **FR-01 (States)** – Four states tracked in `CopilotContext.state` (`Disengaged`, `Engaged`, `AwaitingResponse`, `Alarming`). Only actual state changes are written to `state_log.csv`.
- **FR-02 (Autonomous driving)** – Lidar emergency braking is evaluated first, regardless of current mode; camera features (lane keeping + cruise control) are only active in `Engaged` state. Emergency braking short-circuits further processing.
- **FR-03 (Attentiveness monitoring)** – Time-based transitions are checked at the head of every event dispatch. An attentiveness prompt fires when 120 s have elapsed since the last reset; if no valid response (≤ 3 N) arrives within the 5 s window, the system enters `Alarming` and emits an alarm command.
- **FR-04 (Driver override)** – Any `STEERING_FORCE` event with value > 10 N immediately transitions to `Disengaged` from any state.
- **FR-05 (Data ingestion)** – Both input files are read and merged in ascending timestamp order before the main loop begins.

### Output Files

- `state_log.csv` – every actual state transition with timestamp, from/to states, and trigger label.
- `commands_log.csv` – every actuator command (braking, steering motor, speed, steering wheel prompt, alarm).
- `feature_decision.csv` – every evaluated feature decision (emergency braking, lane keeping, cruise control).

### Design Notes

- No third-party dependencies; the implementation uses only the Python standard library (`csv`, `argparse`, `dataclasses`, `enum`).
- Runs on any POSIX-compliant OS and Windows without hardware or network access.
- All timing logic (120 s attentiveness interval, 5 s response window) uses floating-point event timestamps, making it fully deterministic and testable by injecting synthetic event streams.
