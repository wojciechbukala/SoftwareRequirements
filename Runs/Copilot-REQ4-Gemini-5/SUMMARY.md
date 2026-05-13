```bash
python copilot.py --input /tmp/input --output /tmp/output
```
This Copilot program simulates an onboard computer for advanced driver assistance systems. It processes sensor data (Lidar, Camera) and driver events (Engage, Disengage, Steering Force) to determine the vehicle's autonomous state, maintain safe driving conditions, and monitor driver attentiveness.

The system's behavior is based on the provided Alloy model, including state transitions (Disengaged, Engaged, AwaitingResponse, Alarming), and handling of events such as emergency braking, lane keeping, cruise control, and attentiveness checks.

Input and output are handled via CSV files, specified through command-line arguments. The program ensures robustness by handling missing input files gracefully.
