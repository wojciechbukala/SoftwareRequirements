```bash
python copilot.py --input ./input_data --output ./output_data
```

This project implements the Copilot driver-assistance system simulation based on the provided `REQUIREMENTS.md` specification.

**Key Features Implemented:**

*   **Command-Line Interface (CLI):** The system accepts `--input` and `--output` directory paths via command-line arguments.
*   **Data Ingestion:** Reads `sensor_log.csv` and `driver_events.csv` from the input directory. Events are merged and sorted by timestamp for sequential processing.
*   **State Machine:** Manages the system's operational states: `Disengaged`, `Engaged`, `AwaitingResponse`, and `Alarming`.
*   **Emergency Braking (FR-02, PF-01):** High-priority safety feature triggered by Lidar readings less than 5 meters. It logs a feature decision and issues a braking command, then bypasses further feature evaluation for that cycle.
*   **Autonomous Driving Logic (FR-02):** In `Engaged` mode, it processes camera sensor data to determine (dummy) lane keeping corrections and cruise control adjustments, logging feature decisions and actuator commands. When `Disengaged`, it logs sensor data but takes no further action.
*   **Driver Attentiveness Monitoring (FR-03):** In `Engaged` mode, it issues attentiveness prompts (small steering wheel movements) every 120 seconds, transitioning to `AwaitingResponse`. If no valid response (steering force <= 3N) is received within 5 seconds, it transitions to `Alarming` and issues a continuous alarm. A valid response returns the system to `Engaged` mode and resets the timer. Steering forces between 3N and 10N are ignored.
*   **Driver Override (FR-04):** A steering force greater than 10N immediately transitions the system to `Disengaged` mode, regardless of the current state.
*   **Output Logging:** Generates `state_log.csv`, `commands_log.csv`, and `feature_decision.csv` in the specified output directory, adhering to the defined CSV schemas.
*   **Real-time Status Updates:** Provides verbose output to `stdout` detailing state changes, commands, and feature decisions.

**Design Principles:**

*   The code demonstrates separation of concerns by using distinct functions and classes for input/output, state management, and decision logic.
*   Enumerations (`Enum`) are used for system states, sensor types, and driver event types to enhance readability and maintainability.
*   Error handling for `ValueError` in parsing driver event values ensures robustness for mixed string/float values.

**Missing/Simplified Aspects:**

*   Schema validation for input CSVs is basic (relying on `DictReader` and type casting) and could be made more explicit with dedicated validation logic.
*   The actual calculations for "lane keeping correction" and "cruise control adjustment" are simplified with dummy values (e.g., `data_value * 0.1`) as the requirements focused on the logic flow rather than specific physics models.
