```bash
python copilot.py --input /path/to/input_data --output /path/to/output_logs
```

This document summarizes the implementation of the Copilot driver-assistance system simulation as per the `REQUIREMENTS.md` specification.

**Implemented Features:**

*   **CLI Argument Parsing:** The system accepts `--input` and `--output` directory paths via command-line arguments using `argparse`.
*   **CSV Input/Output:** Utility functions `read_csv_file` and `write_csv_file` handle reading `sensor_log.csv` and `driver_events.csv`, and writing `state_log.csv`, `commands_log.csv`, and `feature_decision.csv` respectively.
*   **Event Merging and Sorting:** All sensor and driver events are read, converted to `datetime` objects for timestamps, merged into a single list, and sorted in ascending order by timestamp for sequential processing.
*   **System State Management:** The `Copilot` class maintains the system's current state (Disengaged, Engaged, AwaitingResponse, Alarming) and handles state transitions according to FR-01, FR-03, and FR-04.
*   **Emergency Braking (FR-02, PF-01):** Implemented to prioritize Lidar readings. If a Lidar distance is < 5 meters, emergency braking is triggered, a command is logged, and further feature processing for that cycle is abandoned.
*   **Autonomous Driving Logic (FR-02, PF-01):** When in `Engaged` mode and a camera sensor event occurs, placeholder logic calculates lane keeping and cruise control adjustments, logging corresponding commands and feature decisions. In `Disengaged` mode, these features are logged as "Ignored".
*   **Attentiveness Monitoring (FR-03):**
    *   In `Engaged` mode, an attentiveness prompt is issued every 120 seconds, transitioning the system to `AwaitingResponse`.
    *   In `AwaitingResponse`, the system waits for 5 seconds for a valid steering force response (<= 3N). A valid response transitions to `Engaged` and resets the timer. Responses > 3N and <= 10N are ignored.
    *   If no valid response is received within 5 seconds, the system transitions to `Alarming` and issues a continuous alarm command.
    *   From `Alarming`, a steering force <= 3N transitions the system back to `Engaged`.
*   **Driver Override (FR-04):** A steering force event > 10N immediately transitions the system to `Disengaged` mode, resetting attentiveness timers.
*   **Logging:** Detailed logs for state transitions (`state_log.csv`), actuator commands (`commands_log.csv`), and feature decisions (`feature_decision.csv`) are generated. State transitions are only logged when an actual state change occurs.
*   **Clean Code and Modularity:** The system uses `Enum` for states and event types, and logic is encapsulated within the `Copilot` class and helper functions to promote readability and maintainability.

The simulation processes events chronologically, with attentiveness checks performed at each event timestamp to correctly manage timers and state transitions.
