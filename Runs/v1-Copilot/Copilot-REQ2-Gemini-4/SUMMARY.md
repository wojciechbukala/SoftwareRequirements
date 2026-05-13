```bash
python copilot.py --input ./input_data --output ./output_results
```

The `copilot.py` script implements a simulation of a driver-assistance system. It processes sensor and driver events from CSV files, manages the system's autonomous state, and logs state transitions, feature decisions, and actuator commands to output CSV files.

**Key Features Implemented:**
-   **CLI Argument Parsing**: Configurable input and output directories.
-   **CSV Handling**: Utilities for reading input event files (`sensor_log.csv`, `driver_events.csv`) and writing output logs (`state_log.csv`, `commands_log.csv`, `feature_decision.csv`).
-   **Event Merging and Sorting**: Combines and sorts sensor and driver events by timestamp for sequential processing.
-   **State Machine**: Manages the system's state (`Disengaged`, `Engaged`, `AwaitingResponse`, `Alarming`) with defined transitions.
-   **Emergency Braking**: High-priority safety feature triggered by Lidar readings below 5 meters.
-   **Autonomous Driving Logic**: Placeholder logic for lane keeping and cruise control when in `Engaged` mode.
-   **Attentiveness Monitoring**: Periodically prompts the driver for attention and transitions to `AwaitingResponse` or `Alarming` state based on driver interaction.
-   **Driver Override**: Immediate disengagement if a strong steering force is detected.
-   **Real-time Output**: Prints status updates to the console during execution.
