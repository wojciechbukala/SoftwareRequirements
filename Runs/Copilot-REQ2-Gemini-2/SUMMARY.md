```bash
python copilot.py --input <path_to_input_directory> --output <path_to_output_directory>
```

This document summarizes the implementation of the Copilot driver-assistance system based on the provided requirements.

### **Implemented Modules:**

1.  **`copilot.py`**: The main entry point of the simulation. It handles command-line argument parsing for input and output directories, reads sensor and driver event data from CSV files, merges and sorts these events by timestamp, orchestrates the simulation by processing each event through the `Copilot` logic, and finally writes the generated state, command, and feature decision logs to CSV files.
2.  **`constants.py`**: Defines various enums and constants used throughout the system. This includes:
    *   `SystemState`: `DISENGAGED`, `ENGAGED`, `AWAITING_RESPONSE`, `ALARMING`.
    *   `SensorType`: `LIDAR`, `CAMERA`.
    *   `DriverEventType`: `ENGAGE`, `DISENGAGE`, `STEERING_FORCE`.
    *   `ActuatorID`: `BrakingSystem`, `SteeringMotor`, `Alarm`.
    *   `Feature`: `EmergencyBraking`, `LaneKeeping`, `CruiseControl`.
    *   Thresholds for emergency braking distance, attentiveness prompt intervals, response windows, and driver override force.
    *   CSV header definitions for all input and output files.
3.  **`csv_utils.py`**: Provides utility functions for reading from and writing to CSV files. It includes `read_csv` for reading with header validation and `write_csv` for writing data to a specified path with given headers.
4.  **`data_models.py`**: Defines dataclasses for structured representation of events and log entries:
    *   `SensorEvent`: Represents a single sensor reading.
    *   `DriverEvent`: Represents a single driver interaction.
    *   `MergedEvent`: A wrapper to combine `SensorEvent` and `DriverEvent` into a single stream, with a custom comparison for sorting by timestamp.
    *   `StateLogEntry`, `CommandLogEntry`, `FeatureDecisionEntry`: Dataclasses for the simulation's output logs.
5.  **`copilot_logic.py`**: Contains the core `Copilot` class, which implements the state machine and event handling logic. Key responsibilities include:
    *   Managing the current system state and logging state transitions (`_log_state_change`).
    *   Logging actuator commands (`_log_command`) and feature decisions (`_log_feature_decision`).
    *   Implementing emergency braking logic, which takes precedence over other features and is always active (`_handle_emergency_braking`).
    *   Managing driver attentiveness checks, including prompting, waiting for responses, and triggering alarms (`_handle_attentiveness_check`).
    *   Processing all incoming events (`process_event`) by dispatching them to appropriate handlers based on type and current system state, adhering to the specified priorities and state transition rules (e.g., driver override, attentiveness response).

### **Functional Requirements Addressed:**

*   **FR-01 (System State and Mode Transitions):** Implemented using the `SystemState` enum and `_log_state_change` method in `Copilot` class.
*   **FR-02 (Autonomous Driving Logic and Priority):** Emergency braking logic is prioritized in `_handle_emergency_braking`. Lane keeping and cruise control are handled for camera events in `ENGAGED` mode. Logging of decisions and commands is integrated.
*   **FR-03 (Attentiveness Monitoring and Alarm):** Handled by `_handle_attentiveness_check` and `process_event` methods, managing `AWAITING_RESPONSE` and `ALARMING` states and transitions.
*   **FR-04 (Driver Override):** Implemented in `process_event` to immediately transition to `DISENGAGED` if steering force exceeds the threshold.
*   **FR-05 (Data Ingestion and Command Output):** Handled by `copilot.py` using `csv_utils.py` for reading/writing and `data_models.py` for structured event parsing.

### **Processing Flows Addressed:**

*   **PF-01 (Sensor event):** The `process_event` method in `Copilot` correctly evaluates emergency braking first for Lidar events, then proceeds to other features for camera events in `ENGAGED` mode.
*   **PF-02 (Loop execution flow):** The main loop in `copilot.py` reads, merges, sorts, and iterates through all events, dispatching them to the `Copilot` instance for processing.

### **Non-Functional Requirements Considerations:**

*   **Design Constraints:** The code is structured into separate modules (`constants`, `csv_utils`, `data_models`, `copilot_logic`) to clearly separate concerns (perception, decision logic, actuator control, data handling). Python's dataclasses and enums contribute to clean code.
*   **Maintainability:** The modular design and use of clear variable names, comments, and type hints aim to improve maintainability.
*   **Portability:** The solution is implemented in pure Python, using standard libraries, making it highly portable across POSIX-compliant systems and Windows without specialized hardware or external databases.

### **Future Work / Missing Items (Not part of the current request but good to note):**

*   **Unit Tests:** While not explicitly requested for implementation, comprehensive unit tests for each module and the `Copilot` class would significantly enhance robustness and maintainability.
*   **Placeholder Logic:** The lane keeping and cruise control calculation logic (`event.data_value * 0.1`, `event.data_value * 0.05`) are placeholders and would need to be replaced with actual algorithmic implementations based on detailed specifications.
*   **Error Handling Refinements:** More specific error handling for malformed data values within CSV rows could be added.
