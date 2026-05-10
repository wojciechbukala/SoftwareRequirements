```bash
python copilot.py --input <input_directory> --output <output_directory>
```

This document summarizes the implementation of the Copilot driver-assistance system.

### Implemented Features:

*   **System States and Transitions (FR-01, FR-03, FR-04):** The system accurately manages transitions between `Disengaged`, `Engaged`, `AwaitingResponse`, and `Alarming` states, logging each change to `state_log.csv`.
*   **Emergency Braking (FR-02, PF-01):** High-priority emergency braking is triggered by Lidar readings below 5 meters. This takes precedence over other autonomous features, issuing a braking command to `commands_log.csv` and recording the decision in `feature_decision.csv`.
*   **Autonomous Driving Logic (FR-02, PF-01):** In `Engaged` mode, camera sensor readings lead to computations for lane keeping and cruise control, with corresponding commands sent to `SteeringMotor` and `SpeedActuator`, and decisions logged. In `Disengaged` mode, sensor data is logged, but no commands or decisions are made.
*   **Attentiveness Monitoring (FR-03):** The system issues attentiveness prompts every 120 seconds when `Engaged`, transitioning to `AwaitingResponse`. It waits 5 seconds for a valid driver response (steering force <= 3N) to return to `Engaged`. Failure to respond within the window leads to `Alarming` state and an alarm command. A valid response in `Alarming` state disarms the alarm and returns to `Engaged`.
*   **Driver Override (FR-04):** A steering wheel force exceeding 10N immediately transitions the system to `Disengaged` state, ensuring manual control.
*   **Data Ingestion and Output (FR-05, PF-02):** The system reads events from `sensor_log.csv` and `driver_events.csv`, merges them, and processes them in ascending timestamp order. Output logs (`state_log.csv`, `commands_log.csv`, `feature_decision.csv`) are generated in the specified CSV format.
*   **Command-Line Interface (Usability):** The application supports `--input` and `--output` arguments for configurable file paths, adhering to the specified CLI requirements.

### Design and Code Structure:

*   **Modularity:** The code is organized into classes (`Event`, `SensorEvent`, `DriverEvent`, `StateLog`, `CommandLog`, `FeatureDecisionLog`, `Copilot`) and utility functions for clear separation of concerns (data structures, CSV parsing/writing, and core simulation logic).
*   **Enums:** Enums are used for `CopilotState`, `SensorType`, `DriverEventType`, `FeatureType`, and `ActuatorId` to improve readability and maintainability.
*   **Timestamp Handling:** Timestamps are parsed into `datetime` objects for accurate chronological processing and time-based logic (e.g., attentiveness timers).
*   **Error Handling:** Basic error handling is included for malformed CSV rows during input parsing.

### How to Run:

To execute the Copilot simulation, use the following command, replacing `<input_directory>` with the path to your directory containing `sensor_log.csv` and `driver_events.csv`, and `<output_directory>` with the desired location for the output CSV files:

```bash
python copilot.py --input <input_directory> --output <output_directory>
```
