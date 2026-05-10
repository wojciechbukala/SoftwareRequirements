```bash
python copilot.py --input <input_directory> --output <output_directory>
```
This program simulates the Copilot driver-assistance system as per the `REQUIREMENTS.md` specification.

**Key Features Implemented:**

*   **Input Processing:** Reads `sensor_log.csv` and `driver_events.csv`, merges them, and processes events in chronological order.
*   **State Management:** Implements `DISENGAGED`, `ENGAGED`, and `ATTENTIVENESS_PENDING` states with appropriate transitions.
*   **Emergency Braking:** Always active, triggered by Lidar readings below 5m.
*   **Attentiveness Check:** In engaged mode, prompts the driver every 120 seconds with a small steering wheel movement. Monitors for driver response within 5 seconds and activates an alarm if no valid response is received.
*   **Disengagement Logic:** Disengages Copilot if a steering wheel force greater than 10N is detected. Driver-initiated disengagement is also handled.
*   **Feature Decisions & Commands:** Logs decisions for emergency braking, lane keeping, and cruise control, and records commands issued to actuators.
*   **Output Generation:** Creates `state_log.csv`, `commands_log.csv`, and `feature_decision.csv` with specified headers and content.

**Assumptions / Simplifications:**

*   **Lane Keeping & Cruise Control:** For `ENGAGED` mode, placeholder commands and decisions are logged for "Steering System" (`ADJUST_LANE`) and "Engine Control" (`ADJUST_SPEED`) respectively. Specific algorithms for these features are not implemented as they were not detailed in the requirements.
*   **Attentiveness Alarm Deactivation:** The alarm is deactivated upon a valid driver response, driver-initiated disengagement, or high steering force disengagement.
*   **Event Timestamps:** Assumes input timestamps are sufficiently granular to determine event order accurately.
*   **Output File Overwriting:** Existing output files in the specified directory will be overwritten.
