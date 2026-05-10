```
copilot --input <input_dir> --output <output_dir>
```

## Implementation

A single Python 3 script at `/workspace/copilot` (executable, no dependencies beyond stdlib).

### Architecture

**`Copilot` class** drives the simulation as a state machine with three states:

| State | Description |
|-------|-------------|
| `DISENGAGED` | Default; only emergency braking is active |
| `ENGAGED` | All three features active; attentiveness timer running |
| `ALARM` | Attentiveness timeout expired; alarm active, all features still running |

**Input merging**: events from `sensor_log.csv` and `driver_events.csv` are merged into a single list sorted by ascending timestamp.

**Timer handling (`_advance_timers`)**: called before each event is processed, this method fires virtual-timestamped events that fell between the previous event and the current one:
1. Attentiveness check command issued at exactly `engaged_time + 120 s` (or last valid response + 120 s).
2. Alarm triggered at exactly `prompt_time + 5 s` if no valid response arrived.

All logged timestamps for timer-driven commands and state transitions reflect when they *logically occurred*, not when the next event was received.

### Feature logic

| Sensor type | Feature | Mode |
|-------------|---------|------|
| `lidar` | Emergency braking (`BRAKE`/`NO BRAKE`) | Always |
| `lidar` | Cruise control (throttle adjustment) | `ENGAGED` or `ALARM` |
| `camera` | Lane keeping (correction value) | `ENGAGED` or `ALARM` |

### Attentiveness check rules

- Prompt issued every 120 s while engaged (`ATTENTIVENESS_CHECK` → `Steering Wheel`).
- Steering force ≤ 3 N within 5 s window: valid response → timer restarted from response time.
- Steering force > 3 N and < 10 N: ignored, system keeps waiting.
- No response within 5 s: `ALARM` state, `ALARM_ON` command issued.
- In `ALARM` state, any valid response (force ≤ 3 N) → `ALARM_OFF`, back to `ENGAGED`.
- Steering force > 10 N: immediate disengagement at any time, any state.

### Output files

| File | Content |
|------|---------|
| `state_log.csv` | Each actual state transition: timestamp, previous_state, current_state, trigger_event |
| `commands_log.csv` | Every actuator command: timestamp, actuator_id, values |
| `feature_decision.csv` | Every feature evaluation: timestamp, feature, decision |
