```bash
python copilot.py --input <input_directory> --output <output_directory>
```
The `copilot.py` script implements a driver-assistance system simulation. It processes sensor and driver events from CSV files, manages system states (Disengaged, Engaged, AwaitingResponse, Alarming), and generates output logs for state transitions, actuator commands, and feature decisions.

Key features implemented include:
- **State Management:** Transitions between `Disengaged`, `Engaged`, `AwaitingResponse`, and `Alarming` states based on events.
- **Emergency Braking:** High-priority braking triggered by Lidar readings below 5 meters, active regardless of system state.
- **Attentiveness Monitoring:** In `Engaged` mode, prompts the driver every 120 seconds. If no valid response within 5 seconds, it transitions to `Alarming` state.
- **Driver Override:** A steering force greater than 10N immediately disengages the system.
- **Autonomous Features:** In `Engaged` mode, processes camera sensor data for lane keeping and cruise control, issuing corresponding actuator commands.
- **Input/Output:** Reads `sensor_log.csv` and `driver_events.csv`, and writes `state_log.csv`, `commands_log.csv`, and `feature_decision.csv` to a specified output directory.
- **Event Processing:** All events are merged and processed in ascending timestamp order.
