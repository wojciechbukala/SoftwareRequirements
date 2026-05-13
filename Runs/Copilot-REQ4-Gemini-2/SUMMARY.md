```bash
python copilot.py --input <input_directory> --output <output_directory>
```

This project implements the Copilot system, a simulation of an onboard computer for advanced driver assistance, as specified in `REQUIREMENTS.md`.

**Key Features Implemented:**

*   **State Machine:** The core logic follows a state machine (Disengaged, Engaged, AwaitingResponse, Alarming) defined in the Alloy model, handling transitions based on sensor data and driver events.
*   **Event Processing:**
    *   **Driver Events:** `ENGAGE`, `DISENGAGE`, `STEERING_FORCE` with logic for overriding, valid responses, and alarm escapes.
    *   **Sensor Events:** `Lidar` for emergency braking (BRAKE/NO_BRAKE decisions), and `Camera` for lane keeping and cruise control (ADJUST decisions) when the system is engaged.
*   **Internal Logic:** Manages attentiveness checks (`PROMPT_INTERVAL`) and response timeouts (`RESPONSE_WINDOW`), transitioning to `AwaitingResponse` and `Alarming` states, and emitting `AlarmActuator` commands.
*   **CSV Input/Output:** Reads `sensor_log.csv` and `driver_events.csv` for input, and generates `state_log.csv`, `commands_log.csv`, and `feature_decision.csv` as output.
*   **CLI Interface:** Supports command-line arguments `--input` and `--output` for specifying directories, as required.
*   **Discrete Event Simulation:** The `run_simulation` method processes events and internal logic in a discrete, tick-based manner, aligning with the temporal aspects implied by the Alloy model.

**Design Choices:**

*   **Python Standard Library:** Relies primarily on Python's built-in `csv` module and `dataclasses` to avoid external dependencies not listed in the provided `requirements.txt`.
*   **Enums:** Utilizes Python `Enum` for clarity and type safety, directly mapping to the enumerated domains in the Alloy specification.
*   **Clear Separation of Concerns:** Logic is organized into distinct classes (`SystemState`, `Copilot`) and functions (CSV parsers/writers) to improve maintainability.

The implementation aims to accurately reflect the behavioral specification outlined in the `REQUIREMENTS.md` document, ensuring proper state transitions, command emissions, and feature decisions based on the defined thresholds and event types.
