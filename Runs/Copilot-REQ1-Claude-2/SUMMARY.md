```
python3 copilot.py --input <input_dir> --output <output_dir>
```

## Implementation

**Entry points:** `copilot` (shell wrapper) and `copilot.py` — both invoke the same `simulate()` function.

### Architecture

The simulator merges `sensor_log.csv` and `driver_events.csv` into a single event stream sorted by ascending timestamp. It then processes each event through a state machine, with a priority-queue (min-heap) for time-based synthetic events (attentiveness prompts and timeouts).

### State machine

Three states: `disengaged`, `engaged`, `alarm`.

| Transition | Trigger |
|---|---|
| disengaged → engaged | driver `engage` event |
| engaged → disengaged | driver `disengage` event or steering_wheel_force > 10 N |
| engaged → alarm | attentiveness timeout (no valid response within 5 s of prompt) |
| alarm → engaged | valid driver response (force ≤ 3 N) |
| alarm → disengaged | steering_wheel_force > 10 N |

Only actual state changes are written to `state_log.csv`.

### Attentiveness check

While engaged, a prompt (`SteeringWheel` / `small_movement`) is issued every 120 seconds. A 5-second response window then opens:
- Force ≤ 3 N: valid — window closes, 120 s timer restarts from the response time.
- 3 N < force ≤ 10 N: ignored — window stays open.
- Timeout with no valid response: `ALARM` state, `Alarm on` command.
- In `alarm`: same force thresholds apply; ≤ 3 N clears the alarm and restarts the 120 s cycle.

Time events use a lazy-deletion heap (each scheduled event carries a sequence ID; cancellations add the ID to a `cancelled` set).

### Sensor processing

| Sensor type | Always | Engaged / Alarm only |
|---|---|---|
| `lidar` (< 5 m) | BRAKE command → Braking System; BRAKE decision | — |
| `lidar` (≥ 5 m) | NO BRAKE decision | Cruise control: speed factor = min(1, (d−5)/20) → ThrottleActuator |
| `camera` | — | Lane keeping: correction = −data_value → SteeringActuator |

### Output files

- `state_log.csv` — every state transition (previous → current, timestamp, trigger).
- `commands_log.csv` — every actuator command (Braking System, ThrottleActuator, SteeringActuator, SteeringWheel, Alarm).
- `feature_decision.csv` — per-reading decisions for `emergency braking`, `cruise control`, and `lane keeping`.
