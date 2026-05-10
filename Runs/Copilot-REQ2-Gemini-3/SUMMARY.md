```bash
python main.py --input <input_directory> --output <output_directory>
```

This project implements a simulation of a Copilot driver-assistance system as specified in `REQUIREMENTS.md`.

The system processes sensor and driver events from `sensor_log.csv` and `driver_events.csv` respectively. These events are merged and sorted by timestamp for sequential processing.

Key features implemented include:
- **State Management:** The system maintains one of four states: Disengaged, Engaged, AwaitingResponse, and Alarming. State transitions are logged to `state_log.csv`.
- **Autonomous Driving Logic:** In Engaged mode, the system evaluates emergency braking (prioritized for Lidar readings < 5m), lane keeping, and cruise control based on sensor data. Feature decisions are logged to `feature_decision.csv` and actuator commands to `commands_log.csv`.
- **Attentiveness Monitoring:** In Engaged mode, the system periodically (every 120 seconds) prompts the driver for attentiveness. If no valid response (steering force <= 3N) is received within 5 seconds, the system transitions to an Alarming state, issuing a continuous alarm. A valid response returns the system to Engaged state.
- **Driver Override:** A steering wheel force exceeding 10N immediately disengages the system.

The system is implemented as a command-line interface tool, taking input and output directories as arguments. It writes all generated logs to the specified output directory.
