```bash
python3 copilot.py --input /path/to/input_dir --output /path/to/output_dir
```

The `copilot.py` script implements a simulation of a driver-assistance system based on the provided `REQUIREMENTS.md`.

**Key Features Implemented:**

*   **State Management:** The system maintains and transitions between four states: `Disengaged`, `Engaged`, `AwaitingResponse`, and `Alarming`, logging all state changes to `state_log.csv`.
*   **Event Processing:** It ingests sensor data from `sensor_log.csv` and driver events from `driver_events.csv`, merges them, and processes them in chronological order.
*   **Emergency Braking:** Implements a high-priority emergency braking system triggered by Lidar readings indicating an obstacle closer than 5 meters. This function operates regardless of the system's engaged state, logging decisions to `feature_decision.csv` and commands to `commands_log.csv`.
*   **Autonomous Driving:** When in the `Engaged` state, the system processes camera sensor data to simulate lane-keeping and cruise control, issuing commands to the Steering Motor and Speed Actuator, and logging corresponding feature decisions and commands.
*   **Driver Attentiveness Monitoring:** In the `Engaged` state, the system periodically (every 120 seconds) prompts the driver for attentiveness. If no valid response (steering force <= 3N) is detected within 5 seconds, it transitions to an `Alarming` state, issuing an alarm command.
*   **Driver Override:** A strong steering force (>10N) from the driver immediately disengages the system, ensuring driver control precedence.
*   **CLI Interface:** The script supports command-line arguments `--input` and `--output` to specify input and output directory paths, respectively.
*   **Logging:** All state transitions, actuator commands, and feature decisions are logged to designated CSV files (`state_log.csv`, `commands_log.csv`, `feature_decision.csv`) in the specified output directory.
