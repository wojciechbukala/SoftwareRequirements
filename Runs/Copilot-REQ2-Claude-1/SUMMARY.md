```
python3 copilot.py --input <input_dir> --output <output_dir>
```

## Implementation

Single-file Python implementation (`copilot.py`) with no external dependencies.

### Architecture

Three clearly separated layers per the design constraint (FR-02, Section 3.5):

- **Perception layer** — `parse_sensor_log`, `parse_driver_events`, `merge_events`: reads and merges the two CSV input streams into a unified timestamp-ordered event list.
- **Decision logic layer** — `handle_sensor_event`, `handle_driver_event`, `_check_time_based_transitions`, `CopilotContext`: implements all state-machine rules, feature evaluations, and timer checks.
- **Actuator/output layer** — `OutputWriter`: buffers all state-transition records, actuator commands, and feature decisions, then writes the three output CSV files on flush.

### State Machine

States: `Disengaged` (initial) → `Engaged` → `AwaitingResponse` → `Alarming`.

| Trigger | Transition |
|---|---|
| ENGAGE driver event | Disengaged → Engaged |
| DISENGAGE driver event | any → Disengaged |
| Steering force > 10 N (FR-04) | any → Disengaged |
| 120 s elapsed in Engaged (FR-03) | Engaged → AwaitingResponse + prompt command |
| Steering force ≤ 3 N in AwaitingResponse | AwaitingResponse → Engaged |
| 5 s timeout in AwaitingResponse (FR-03) | AwaitingResponse → Alarming + alarm command |
| Steering force ≤ 3 N in Alarming | Alarming → Engaged |
| Steering force 3–10 N in AwaitingResponse | ignored (stay in AwaitingResponse) |

### Feature Evaluation (PF-01)

- **Lidar**: emergency braking evaluated first, in every state. Distance < 5 m → `BRAKE` decision + `BrakingSystem` command; otherwise `NO_BRAKE` decision.
- **Camera**: lane-keeping and cruise-control features evaluated only when `Engaged`. Issues `SteeringMotor` and `SpeedActuator` commands and logs corresponding feature decisions.

### Output Files

All written to `--output` directory with UTF-8 CSV encoding and a header row:

| File | Contents |
|---|---|
| `state_log.csv` | Actual state changes only (timestamp, previous_state, current_state, trigger_event) |
| `commands_log.csv` | All actuator commands (timestamp, actuator_id, values) |
| `feature_decision.csv` | All feature evaluations (timestamp, feature, decision) |

### CLI

```
python3 copilot.py --input <dir> --output <dir>
```

Both arguments are mandatory. The output directory is created automatically if absent. Real-time status is printed to stdout during processing.
