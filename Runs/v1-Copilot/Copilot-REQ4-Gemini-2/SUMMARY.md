```
python copilot.py --input <input_directory> --output <output_directory>
```
The `copilot.py` script implements a simulation of an advanced driver assistance system based on the provided `REQUIREMENTS.md`.

**Key features implemented:**

*   **CLI Argument Parsing:** Uses `argparse` to accept `--input` and `--output` directory paths.
*   **Enums and Data Structures:** Defines Python `Enum` classes for `State`, `SensorType`, `DriverEventType`, `FeatureDecisionKind`, `DecisionValue`, and `Actuator`, and `dataclass`es for `Event`, `SensorEvent`, `DriverEvent`, `StateLogEntry`, `Command`, and `FeatureDecision` to represent system entities and logs.
*   **System State Management:** A `SystemState` class tracks the current operational state, time, and relevant timers (`last_prompt`, `awaiting_since`). It also accumulates generated `state_log`, `commands_log`, and `feature_decision_log` entries.
*   **CSV Input/Output:** Functions to read sensor and driver events from `sensor_log.csv` and `driver_events.csv` respectively, and to write simulation results to `state_log.csv`, `commands_log.csv`, and `feature_decision.csv`. All I/O adheres to the specified CSV format (comma-separated, UTF-8, header row).
*   **Discrete Event Simulation Loop:** The `run_simulation` method orchestrates the simulation as a discrete event system:
    1.  All input events are read and sorted chronologically.
    2.  The simulation advances time step by step (one unit per tick).
    3.  At each `current_time` tick:
        *   All external events (sensor and driver events) scheduled for that `current_time` are processed.
        *   Internal state transitions (e.g., `Engaged` to `AwaitingResponse` after `PROMPT_INTERVAL`, `AwaitingResponse` to `Alarming` after `RESPONSE_WINDOW`) and continuous actions (e.g., `Alarming` state emitting `AlarmActuator` commands) are evaluated and applied.
    4.  Logs are generated for state changes, commands, and feature decisions.
    5.  The simulation terminates when there are no more pending external events and no internal activities (like prompts, timeouts, or alarms) are expected. A safety limit is included to prevent infinite loops.
*   **Event Handling Logic:** Dedicated methods `_handle_sensor_event` and `_handle_driver_event` encapsulate the logic for processing specific event types, including state transitions, feature decisions, and command emissions based on the Alloy model.
*   **Maintainability:** The code uses clear data structures, enums, and follows the principles of separating concerns (I/O, state management, event handling). Inline comments and docstrings are provided.