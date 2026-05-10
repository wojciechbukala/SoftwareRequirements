```bash
python copilot.py --input <input_directory> --output <output_directory>
```

The `copilot.py` program implements a simulation of a driver-assistance system (Copilot) based on the provided `REQUIREMENTS.md`.

**Key Features Implemented:**

*   **Command-Line Interface (CLI):** Parses `--input` and `--output` directory arguments using `argparse`.
*   **CSV Input/Output:**
    *   Reads `sensor_log.csv` and `driver_events.csv` from the specified input directory.
    *   Merges and sorts all events by timestamp for chronological processing.
    *   Writes `state_log.csv`, `commands_log.csv`, and `feature_decision.csv` to the specified output directory.
*   **State Machine:**
    *   Defines `CopilotState` enumeration: `DISENGAGED`, `ENGAGED`, `ATTENTIVENESS_CHECK_PENDING`, `ALARMING`.
    *   Manages state transitions based on sensor readings and driver events.
*   **Emergency Braking:**
    *   Always active, regardless of engagement state.
    *   Triggers a `BRAKE` command for the "Braking System" actuator and records an "emergency braking" decision when a Lidar reading is `< 5.0m`.
*   **Engagement/Disengagement:**
    *   Driver events "Engage" and "Disengage" correctly transition the system between `DISENGAGED` and `ENGAGED` states.
    *   A steering force `> 10N` from a driver event immediately disengages the system.
*   **Attentiveness Check (Engaged Mode):**
    *   Every 120 seconds, a "SMALL_MOVEMENT" command is issued to the "Steering System" for an attentiveness prompt, transitioning the state to `ATTENTIVENESS_CHECK_PENDING`.
    *   The system waits for 5 seconds for a driver response.
    *   A steering force `<= 3N` within 5 seconds is a valid response, resetting the 120s timer and returning to `ENGAGED`.
    *   If no valid response within 5 seconds, the system transitions to `ALARMING` and issues an "ACTIVATE" command to the "Alarm System".
    *   A steering force `> 3N` and `< 10N` is ignored.
    *   While `ALARMING`, any valid steering response (`<= 3N`) deactivates the alarm and returns to `ENGAGED`.
*   **Feature Decisions & Commands:**
    *   In `ENGAGED` mode, placeholder commands and feature decisions are recorded for "lane keeping" (Camera sensor) and "cruise control" (Lidar sensor).
*   **State Logging:**
    *   State transitions are logged to `state_log.csv` only when an actual change in state occurs.

The `copilot.py` script provides a functional simulation of the described driver-assistance system, handling various sensor inputs, driver events, and state changes as per the requirements.