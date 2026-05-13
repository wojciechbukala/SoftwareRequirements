```bash
python copilot.py --input <input_directory> --output <output_directory>
```

This project implements the Copilot program, an offline simulation of an advanced driver assistance system, based on the provided `REQUIREMENTS.md`.

**Key features implemented:**

*   **Data Structures**: Python `Enum` classes for states, sensor types, driver event types, feature decision kinds, decision values, and actuators, mirroring the Alloy model. Custom classes (`StateLogEntry`, `Command`, `FeatureDecision`, `Event`, `SensorEvent`, `DriverEvent`) are defined for event and log data.
*   **CLI Interface**: The `copilot.py` script accepts `--input` and `--output` directory paths via command-line arguments.
*   **CSV Input/Output**: Functions for reading `sensor_log.csv` and `driver_events.csv`, and writing `state_log.csv`, `commands_log.csv`, and `feature_decision.csv` are implemented, adhering to the specified CSV format.
*   **System State Management**: The `SystemState` class manages the current state of the simulation, including `current_state`, `current_time`, `last_prompt`, and `awaiting_since`, along with lists to store log entries.
*   **Alloy Predicate Translation**: The core logic of the Alloy model's predicates has been translated into Python methods within the `SystemState` class, including:
    *   Initialization (`__init__`)
    *   Time progression (`_tick_time`)
    *   Event processing (`_process_event`)
    *   Log appenders (`_add_state_log`, `_emit_command`, `_emit_feature_decision`)
    *   Event handlers (`handle_engage_driver_event`, `handle_disengage_driver_event`, `handle_steering_force_driver_event`, `handle_lidar_sensor_event`, `handle_camera_sensor_event`)
    *   Internal steps (`internal_step`) for attentiveness checks, timeouts, and alarming.
*   **Simulation Loop**: The `run_simulation` method orchestrates the simulation, processing events chronologically and handling internal state transitions.
