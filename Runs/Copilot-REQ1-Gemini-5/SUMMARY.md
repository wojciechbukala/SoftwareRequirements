```bash
python3 copilot.py --input <input_directory> --output <output_directory>
```

This project implements a Copilot onboard computer simulation as specified in `REQUIREMENTS.md`.

**Key Features Implemented:**

*   **CLI Interface**: The program can be invoked using `copilot.py --input <input_directory> --output <output_directory>`.
*   **Input Processing**: Reads `sensor_log.csv` and `driver_events.csv` from the specified input directory, merges them, and processes events in ascending order of timestamp.
*   **Output Generation**: Writes results to `state_log.csv`, `commands_log.csv`, and `feature_decision.csv` in the specified output directory.
*   **State Management**: Implements `DISENGAGED` and `ENGAGED` states with transitions based on driver events.
*   **Emergency Braking**: Highest priority feature, always active. Triggers braking if Lidar reading is less than 5m.
*   **Attentiveness Checks**: In `ENGAGED` mode, issues steering wheel movement prompts every 120 seconds and monitors for driver response within 5 seconds. Activates/deactivates an alarm based on response.
*   **Lane Keeping and Cruise Control**: Active only in `ENGAGED` mode and when no attentiveness alarm is active. (Placeholder logic for actual correction/adjustment values, as per requirements).
*   **Disengagement**: Immediate disengagement if steering wheel force exceeds 10N.
*   **Robust CSV Parsing**: Handles type conversion for numerical and string values in input CSVs to prevent runtime errors.

**Assumptions and Simplifications:**

*   As the requirements did not specify the actual logic for Lane Keeping and Cruise Control decisions, placeholder values (0.0) are used for these features.
*   The system assumes valid CSV input formats as described in the requirements.

The implementation includes basic logging for state transitions, actuator commands, and feature decisions, adhering to the specified CSV output formats. A basic test scenario (`test_scenario_1`) was used to verify core functionality, including state changes, emergency braking, and basic feature activations.