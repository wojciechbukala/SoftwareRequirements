# Copilot Implementation Summary

## Overview

Implemented the Copilot driver-assistance onboard computer as a single executable Python 3 script (`/workspace/copilot`).

## Usage

```
copilot --input <dir> --output <dir>
```

## Architecture

The system is a single-file Python script built around the `CopilotSystem` class, which maintains a state machine and processes a time-ordered stream of sensor and driver events.

### States

| State | Description |
|-------|-------------|
| `disengaged` | Initial state. Only emergency braking is active. |
| `engaged` | All features active: lane keeping, cruise control, emergency braking, and attentiveness checks. |
| `alarm` | Driver failed attentiveness check. Alarm active; all autonomous features still running. Waiting indefinitely for valid driver response. |

### State Transitions

| From | To | Trigger |
|------|----|---------|
| disengaged | engaged | `engage` driver event |
| engaged | disengaged | `disengage` driver event or steering force > 10 N |
| engaged | alarm | Attentiveness window (5 s) expires with no valid response |
| alarm | engaged | Steering force ≤ 3 N received |
| alarm | disengaged | Steering force > 10 N |

### Sensor Mapping

| `sensor_type` | Feature | Condition |
|---------------|---------|-----------|
| `lidar` | Emergency braking | Always (distance < 5 m → BRAKE, else NO_BRAKE) |
| `camera` | Lane keeping | Engaged or alarm only |
| anything else | Cruise control | Engaged or alarm only |

### Attentiveness Check Logic

1. Every 120 seconds after engagement (or after a valid response), a `attentiveness_prompt` command is sent to the Steering System actuator.
2. A 5-second response window opens.
3. Outcomes:
   - Force ≤ 3 N within window → window cleared, 120-s timer restarted from response time.
   - Force > 3 N and ≤ 10 N → ignored, waiting continues.
   - Window expires with no valid response → `alarm_on` command issued, transition to `alarm`.
4. Force > 10 N at any time → immediate disengagement.

Timer-based events (prompts, alarm activations) are recorded at their exact computed timestamp, not at the timestamp of the triggering event.

### Emergency Braking

Evaluated on every Lidar reading regardless of mode:
- Distance **strictly less than** 5 m → `emergency_brake` command to Braking System + `BRAKE` decision.
- Otherwise → `NO_BRAKE` decision (no command).

## Output Files

| File | Content |
|------|---------|
| `state_log.csv` | Every actual state transition (same-state events omitted). Columns: `timestamp, previous_state, current_state, trigger_event`. |
| `commands_log.csv` | Every actuator command issued. Columns: `timestamp, actuator_id, values`. |
| `feature_decision.csv` | Every autonomous feature evaluation result. Columns: `timestamp, feature, decision`. |

## Implementation Notes

- Events are merged from both input files and sorted by ascending timestamp. Sensor events take priority over driver events at identical timestamps.
- Timestamps are parsed as floats (ISO 8601 strings are also supported via `datetime.fromisoformat`). Output timestamps are formatted as integers when they have no fractional part.
- Input files must be UTF-8 CSV with comma separators and a header row.
