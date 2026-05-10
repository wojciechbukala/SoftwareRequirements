```bash
python3 copilot.py --input <input_directory> --output <output_directory>
```

The Copilot driver-assistance system was implemented in Python. The system processes sensor readings and driver events from CSV input files, manages its state (DISENGAGED, ENGAGED, ALARM), and generates output logs for state transitions, actuator commands, and feature decisions.

Key features implemented:
- **Input Processing**: Reads `sensor_log.csv` and `driver_events.csv`, sorting all events by timestamp for sequential processing.
- **Output Logging**: Writes to `state_log.csv`, `commands_log.csv`, and `feature_decision.csv` with appropriate headers and data.
- **State Management**: Handles transitions between `DISENGAGED`, `ENGAGED`, and `ALARM` states.
- **Emergency Braking**: Always active, triggers braking command and decision if Lidar reading is below 5m, regardless of engagement state.
- **High Steering Force Disengagement**: Immediate disengagement if steering wheel force exceeds 10N.
- **Attentiveness Checks**:
    - In `ENGAGED` mode, issues a "SMALL_MOVEMENT" command to the steering wheel every 120 seconds.
    - Waits for a driver response (steering wheel force <= 3N) within 5 seconds.
    - If no valid response within the window, transitions to `ALARM` state.
    - Ignores responses between 3N and 10N, continuing to wait.
    - Returns to `ENGAGED` from `ALARM` upon a valid steering response.
- **Feature Decisions**: Logs decisions for Lane Keeping (triggered by CAMERA) and Cruise Control (triggered by RADAR) when in `ENGAGED` mode.

Unit tests were developed to cover critical functionalities including state transitions, emergency braking, high steering force disengagement, and various scenarios for attentiveness checks. All tests passed successfully.