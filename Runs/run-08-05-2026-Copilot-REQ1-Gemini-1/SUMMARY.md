```bash
python copilot.py --input <input_directory> --output <output_directory>
```
The `copilot.py` program simulates an onboard computer for a driver-assistance system. It processes sensor readings and driver events from CSV input files, manages system states (Engaged/Disengaged), and logs decisions and commands to CSV output files.

**Key Features Implemented:**
*   **Command Line Argument Parsing:** Uses `argparse` to handle `--input` and `--output` directories for specifying input and output file locations.
*   **CSV Input/Output Handling:** Reads `sensor_log.csv` and `driver_events.csv`, and writes to `state_log.csv`, `commands_log.csv`, and `feature_decision.csv` using Python's `csv` module.
*   **Event Stream Processing:** Merges and sorts all sensor and driver events by timestamp for sequential processing.
*   **State Machine:** Manages `ENGAGED` and `DISENGAGED` states, logging transitions only when an actual state change occurs.
*   **Emergency Braking:** Implemented with highest priority; triggers for Lidar readings below 5m regardless of the system's engagement state, logging a braking command and decision.
*   **Attentiveness Check (Engaged Mode):**
    *   Issues a small steering wheel movement command every 120 seconds.
    *   Monitors for driver response within 5 seconds.
    *   Activates an alarm if no valid response is received.
    *   Resets the 120-second timer upon a valid response (steering force <= 3 N).
    *   Ignores responses between 3 N and 10 N, maintaining the alarm if active.
*   **Disengagement Logic:**
    *   Immediate disengagement occurs if steering wheel force exceeds 10 N.
    *   Explicit `toggle_engagement` events also control engagement/disengagement.
    *   Attentiveness timers and alarms are reset upon disengagement.
*   **Lane Keeping and Cruise Control:** These features are active and log decisions when the system is in `ENGAGED` mode and relevant sensor data is received. The specific decision-making logic for these features is simplified as per the requirements.

**To Run the Program:**
1.  Ensure you have `sensor_log.csv` and `driver_events.csv` files in your `<input_directory>`.
2.  Execute the command provided at the top of this summary, replacing `<input_directory>` and `<output_directory>` with your desired paths.
3.  The output files (`state_log.csv`, `commands_log.csv`, `feature_decision.csv`) will be generated in the specified `<output_directory>`.
