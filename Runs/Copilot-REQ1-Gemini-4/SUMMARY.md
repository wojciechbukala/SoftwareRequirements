```bash
python copilot.py --input <input_directory> --output <output_directory>
```

This implementation provides a Python program, `copilot.py`, that simulates the onboard computer for a driver-assistance system based on the provided `REQUIREMENTS.md`.

**Key Features Implemented:**

*   **Argument Parsing:** Handles `--input` and `--output` command-line arguments for specifying input and output directories.
*   **CSV Input Processing:** Reads `sensor_log.csv` and `driver_events.csv`, merges them, and processes events in ascending chronological order.
*   **State Management:** Implements `DISENGAGED` and `ENGAGED` states for the Copilot system.
*   **Emergency Braking:** High-priority emergency braking is active in all modes, triggered by Lidar readings below 5 meters.
*   **Attentiveness Checks (Engaged Mode):**
    *   Initiates attentiveness prompts every 120 seconds with a small steering wheel movement.
    *   Monitors driver responses within a 5-second window.
    *   Activates an alarm if no valid response is received within the window.
    *   Handles ignored responses and immediate disengagement for high steering forces (>10N).
*   **Lane Keeping and Cruise Control:** Commands are issued in `ENGAGED` mode based on Camera and Radar sensor data, respectively.
*   **CSV Output Generation:** Produces three output CSV files:
    *   `state_log.csv`: Records state transitions.
    *   `commands_log.csv`: Logs commands issued to actuators.
    *   `feature_decision.csv`: Records decisions made by autonomous features.
*   **Robustness:** Includes basic error handling for malformed CSV rows during input reading.

**How to Run:**

To execute the Copilot simulation, use the following command:

```bash
python copilot.py --input /path/to/your/input_data --output /path/to/your/output_results
```

Replace `/path/to/your/input_data` with the directory containing your `sensor_log.csv` and `driver_events.csv` files, and `/path/to/your/output_results` with the desired directory for the output CSV files (`state_log.csv`, `commands_log.csv`, `feature_decision.csv`).
