```bash
python copilot.py --input <path_to_input_dir> --output <path_to_output_dir>
```
The Copilot system has been implemented as a Python command-line interface (CLI) application. The implementation closely follows the provided `REQUIREMENTS.md` and the Alloy model for state transitions, event handling, and decision logic.

**Key Components and Features:**

1.  **`copilot_constants.py`**: Defines all enumerated domains (e.g., `State`, `SensorType`, `DriverEventType`, `Actuator`) and threshold constants (`LIDAR_DANGER`, `PROMPT_INTERVAL`) directly derived from the Alloy model.
2.  **`copilot_csv_handler.py`**: Manages all input and output operations. It provides functions to:
    *   Read `sensor_log.csv` and `driver_events.csv`, performing basic type conversions and validation against defined enums. Named tuples are used for structured event data.
    *   Write `state_log.csv`, `commands_log.csv`, and `feature_decision.csv` in the specified CSV format.
3.  **`copilot_logic.py`**: Contains the core simulation logic within the `CopilotSystem` class.
    *   **State Management**: Tracks `current_state`, `current_time`, `last_prompt`, `awaiting_since`.
    *   **Logging**: Maintains lists for `state_log`, `commands_log`, and `feature_decision_log`.
    *   **Event Handlers**: Implements dedicated methods (`_handle_engage_driver_event`, `_handle_lidar_sensor_event`, etc.) that directly correspond to the Alloy predicates for processing different event types.
    *   **Internal Steps**: The `_internal_step` method handles time-based transitions such as driver attentiveness prompts, response timeouts, and continuous alarming, mirroring the `internalStep` predicate.
    *   **Event Processing Loop**: The `process_all_events` method orchestrates the simulation by sorting all input events by timestamp, processing internal steps between external events, and then applying external event logic.
4.  **`copilot_cli.py`**: The CLI entry point that:
    *   Uses `argparse` to handle `--input` and `--output` directory arguments.
    *   Validates input directories and creates output directories if necessary.
    *   Orchestrates the reading of input, processing by `CopilotSystem`, and writing of output.
    *   Provides clear status updates to the standard output.
5.  **`copilot.py`**: A simple wrapper script to execute the CLI application, making it executable via `python copilot.py`.

The system is designed to be portable and adheres to the specified I/O formats, ensuring it can be verified through black-box assessment against expected outputs. The logic strictly follows the behavior defined in the Alloy model, including specific state transitions and command/decision emissions.
