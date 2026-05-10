```bash
python copilot.py --input <input_directory> --output <output_directory>
```

This project implements the Copilot system, an autonomous driver assistance simulator, based on the provided `REQUIREMENTS.md` specification. The system is developed in Python and simulates the logic of autonomous operations like lane keeping, cruise control, and emergency braking, along with driver attentiveness monitoring.

**Key Features:**

*   **Modular Design:** The system is structured into clear components representing states, events, actuators, and decisions, closely mirroring the provided Alloy model.
*   **Event-Driven Simulation:** It processes a sorted stream of sensor and driver events, advancing a discrete internal clock.
*   **State Management:** The `SystemState` class manages the current operational state (Disengaged, Engaged, AwaitingResponse, Alarming) and handles state transitions according to the Alloy predicates.
*   **Safety-Critical Functions:** Implements emergency braking logic based on Lidar data and driver override detection.
*   **Driver Attentiveness:** Includes mechanisms for prompting driver response and escalating to an alarming state if no adequate response is received within a defined window.
*   **Input/Output Handling:** Reads sensor and driver events from CSV files (`sensor_log.csv`, `driver_events.csv`) and writes state changes, actuator commands, and feature decisions to separate CSV output files (`state_log.csv`, `commands_log.csv`, `feature_decision.csv`).
*   **Command-Line Interface (CLI):** Configurable via `--input` and `--output` command-line arguments for specifying directory paths.
*   **Inline Documentation:** Comprehensive inline comments and docstrings are provided to enhance maintainability, as per the requirements.

The implementation adheres to the system attributes and non-functional requirements outlined in `REQUIREMENTS.md`, focusing on an offline, portable, and maintainable solution.
