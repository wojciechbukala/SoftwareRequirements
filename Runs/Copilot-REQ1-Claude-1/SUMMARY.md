```
python3 copilot.py --input <input_dir> --output <output_dir>
```

## Implementation

A single-file Python implementation (`copilot.py`) of the Copilot driver-assistance onboard computer. Also included is a thin `copilot` wrapper script for direct invocation.

### Architecture

The `Copilot` class implements an event-driven state machine with three states:

- **disengaged** — initial state; only emergency braking is active
- **engaged** — full assistance active (lane keeping, cruise control, emergency braking, attentiveness checks)
- **alarm** — attentiveness check timed out; alarm is active, lane keeping and cruise control continue

### Event Processing

Events from `sensor_log.csv` and `driver_events.csv` are merged into a single stream sorted by ascending timestamp (driver events take precedence in ties). Before each event is processed, `_check_time_events()` fires any elapsed time-based events (attentiveness prompt at `last_reset + 120s`, alarm at `prompt_time + 5s`) using their exact calculated timestamps.

### Features

**Emergency braking** (always active): every Lidar reading is checked; distance < 5 m issues a `BrakingSystem` brake command and records a `BRAKE` decision, otherwise records `no brake`.

**Lane keeping** (engaged/alarm only): camera sensor readings drive a `SteeringWheel` correction command equal to `-data_value`, recorded as a `lane keeping` decision.

**Cruise control** (engaged/alarm only): Lidar readings produce an `Engine` speed adjustment of `distance - 20.0` (negative = slow down, zero = maintain), recorded as a `cruise control` decision.

**Attentiveness check**: every 120 seconds after engagement (or last valid response), a small `SteeringWheel` movement (0.5) is issued. If no valid response (steering force ≤ 3 N) arrives within 5 seconds, the system transitions to `alarm`. Forces between 3 N and 10 N are ignored. A force > 10 N disengages immediately from any state.

### Output Files

- `state_log.csv` — records only actual state changes (previous → current, trigger, timestamp)
- `commands_log.csv` — every actuator command with its timestamp
- `feature_decision.csv` — per-feature decisions for emergency braking, lane keeping, and cruise control
