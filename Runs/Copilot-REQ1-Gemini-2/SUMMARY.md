```bash
python copilot.py --input <input_directory> --output <output_directory>
```

## Summary of Work Done

This program simulates a driver-assistance system, "Copilot," based on the provided requirements. It processes sensor readings and driver events from CSV files, manages the system's state (engaged/disengaged), and generates output logs for state transitions, actuator commands, and autonomous feature decisions.

**Key Features Implemented:**

*   **Command Line Interface:** Accepts `--input` and `--output` directories for file paths.
*   **Input Handling:** Reads `sensor_log.csv` and `driver_events.csv`, merges events, and processes them chronologically.
*   **State Management:** Tracks and transitions between "disengaged" and "engaged" states, logging only actual state changes.
*   **Emergency Braking:** Implemented with highest priority, triggered by Lidar readings below 5m, irrespective of the system's engagement state.
*   **Attentiveness Check:** In engaged mode, a steering nudge is issued every 120 seconds. The system monitors driver steering wheel force responses to maintain engagement, emit alarms, or disengage.
*   **Placeholder Logic for Lane Keeping and Cruise Control:** Basic functionality included for these features when in "engaged" mode, issuing commands based on camera and speed sensor data, respectively.
*   **Output Generation:** Produces three CSV files: `state_log.csv`, `commands_log.csv`, and `feature_decision.csv` with the specified columns.

**Assumptions Made for Undefined Logic:**

*   **Lane Keeping Logic:** Assumed to issue a "Steering" command (e.g., value 1.0) based on 'Camera' sensor readings and record a "KEEP_LANE" decision.
*   **Cruise Control Logic:** Assumed to issue an "Accelerator" command (e.g., value 5.0) based on 'Speed Sensor' readings and record a "MAINTAIN_SPEED" decision.
*   **Attentiveness Check Nudge:** Modeled as a small "Steering" command to the "Steering System" actuator.
*   **Alarm System:** Modeled as commands to an "Alarm System" actuator, turning on when attention is not met, and off when a valid response is received.

The implementation prioritizes clarity and adherence to the explicit requirements, with minimal reasonable assumptions for unspecified behaviors.