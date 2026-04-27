# Copilot Implementation Summary

## What Was Built

A Python simulation of the Copilot driver-assistance system as specified in REQUIREMENTS.md. The program reads sensor and driver event CSVs, processes them through a state machine, and emits three output CSVs.

## Architecture

The codebase is organised around three layers (section 3.5 design constraint):

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Perception | `copilot/ingestion.py` | Reads `sensor_log.csv` and `driver_events.csv`; merges them into a unified ascending-timestamp stream (PF-02) |
| Decision logic | `copilot/state_machine.py`, `copilot/features.py` | State machine (FR-01 – FR-04), feature evaluation (emergency braking, lane keeping, cruise control) |
| Actuator control | `copilot/actuators.py` | Named actuator IDs and command-value builders |
| Output | `copilot/output.py` | Buffers records in memory; flushes all three output CSVs atomically at end of run |

`copilot/__main__.py` is the CLI entry point (`python -m copilot` or the `copilot` script installed by `setup.py`).

## Key Design Decisions

### Event-driven timers
Because the simulation processes a discrete event stream there is no background clock. Timer-based transitions (120 s attentiveness interval, 5 s response window) are evaluated at the start of every event's processing by `_check_timers()`, which fires any overdue transitions before the actual event is handled.

### Emergency braking is always active
Per FR-02 and PF-01 the Lidar emergency-braking evaluation runs regardless of operating mode. A `BRAKE` decision writes both a feature decision row and a `BrakingSystem` command; a `NO_BRAKE` decision writes only the feature decision row.

### Camera features are mode-gated
Lane keeping and cruise control are only evaluated (and commanded) when the system is in the `Engaged` state (PF-01).

### Force thresholds
| Force (N) | Behaviour |
|-----------|-----------|
| ≤ 3 | Valid attentiveness response; exits AwaitingResponse or Alarming → Engaged |
| > 3 and ≤ 10 | Ignored in AwaitingResponse; no effect otherwise |
| > 10 | Driver override; immediate transition to Disengaged from any state (FR-04) |

## How to Run

```bash
# Install (creates the `copilot` console script)
python3 -m venv .venv
.venv/bin/pip install -e .

# Run
.venv/bin/copilot --input <input_dir> --output <output_dir>
# or without installation:
.venv/bin/python -m copilot --input <input_dir> --output <output_dir>
```

### Input files (in `<input_dir>`)
- `sensor_log.csv` — `timestamp,sensor_id,sensor_type,data_value,unit`
- `driver_events.csv` — `timestamp,event_type,value`

### Output files (written to `<output_dir>`)
- `state_log.csv` — every state transition with its trigger
- `commands_log.csv` — every actuator command issued
- `feature_decision.csv` — every autonomous feature outcome

## Requirements Coverage

| Requirement | Status |
|-------------|--------|
| FR-01 State machine (Disengaged / Engaged / AwaitingResponse / Alarming) | Implemented in `state_machine.py`; same-state events not logged |
| FR-02 Emergency braking always; camera features in Engaged only | `features.py` + `state_machine.py` |
| FR-03 120 s attentiveness prompt → AwaitingResponse → 5 s window → Alarming; ≤ 3 N escape from Alarming | `state_machine.py` `_check_timers` + `_handle_steering_force` |
| FR-04 > 10 N override → Disengaged from any state | `_handle_steering_force` |
| FR-05 Reads sensor_log.csv and driver_events.csv; merged ascending order | `ingestion.py` |
| PF-01 Sensor processing flow | `_handle_sensor` |
| PF-02 Loop execution | `__main__.py` `run()` |
| Section 3.4 CLI `--input / --output` | `__main__.py` `build_parser()` |
| Section 3.5 CSV headers, UTF-8, comma separator | `output.py` |
