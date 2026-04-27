# Copilot System — Implementation Summary

## What Was Built

A command-line simulation of the Copilot driver-assistance system, implemented in Python 3 as the package `copilot/`.  It ingests time-ordered sensor and driver events, runs a state machine, and produces three CSV output files.

## How to Run

```
python3 -m copilot --input <input-dir> --output <output-dir>
```

Or, after `pip install -e .`:

```
copilot --input <input-dir> --output <output-dir>
```

`<input-dir>` must contain `sensor_log.csv` and `driver_events.csv`.  
`<output-dir>` will be created if it does not exist and will receive `state_log.csv`, `commands_log.csv`, and `feature_decision.csv`.

## Architecture

The source is split into four layers as required by FR-3.5:

| Module | Layer | Responsibility |
|---|---|---|
| `perception.py` | Perception | Reads and parses `sensor_log.csv` / `driver_events.csv`; merges events into a single ascending-timestamp stream |
| `decision.py` | Decision logic | Evaluates emergency braking (Lidar), lane-keeping correction, and cruise-control adjustment (camera) |
| `actuator.py` | Actuator control | Constructs typed `ActuatorCommand` objects for BrakingSystem, SteeringMotor, SpeedActuator, SteeringWheel, and Alarm actuators |
| `output.py` | Output | Opens, writes, and closes all three output CSV files |
| `state_machine.py` | Orchestration | Drives the Disengaged / Engaged / AwaitingResponse / Alarming state machine; calls perception, decision, actuator, and output in the correct order |
| `cli.py` / `__main__.py` | CLI | Argument parsing, real-time status printing, top-level coordination |

## Requirements Coverage

| Requirement | Implementation |
|---|---|
| **FR-01** States & transitions | `State` enum in `state_machine.py`; only actual state changes are written to `state_log.csv` |
| **FR-02** Autonomous driving & priority | Lidar evaluated first in `_process_lidar`; camera evaluated only when `ENGAGED`; all decisions and commands logged |
| **FR-03** Attentiveness monitoring | `_check_time_based_transitions` fires the 120 s prompt before each event; 5 s timeout checked on the next event after entering `AwaitingResponse`; alarm command emitted on timeout |
| **FR-04** Driver override | `STEERING_FORCE > 10 N` transitions any state to `Disengaged` before other force rules are evaluated |
| **FR-05** Data ingestion | Events from both CSVs are merged and processed in ascending timestamp order; tie-breaking places sensor events before driver events |
| **PF-01** Sensor event flow | Lidar → emergency braking (always); camera → lane keeping + cruise control (Engaged only); both record feature decisions and actuator commands |
| **PF-02** Loop execution | `load_events` merges the two streams; `run()` in `cli.py` iterates the merged stream and dispatches each event |
| **3.4** CLI interface | `--input` and `--output` are mandatory CLI arguments; real-time status is printed to stdout |
| **3.5** CSV format | All files use comma separator, UTF-8 encoding, and the exact headers specified in the requirements |

## Output File Formats

**state_log.csv**
```
timestamp,previous_state,current_state,trigger_event
```
Trigger values: `ENGAGE`, `DISENGAGE`, `ATTENTIVENESS_PROMPT`, `VALID_RESPONSE`, `RESPONSE_TIMEOUT`, `ALARM_CLEARED`, `STEERING_OVERRIDE`

**commands_log.csv**
```
timestamp,actuator_id,values
```
Actuator IDs: `BrakingSystem` (`FULL_BRAKE`), `SteeringMotor` (float correction), `SpeedActuator` (float adjustment), `SteeringWheel` (`ATTENTIVENESS_PROMPT`), `Alarm` (`CONTINUOUS_ALARM`)

**feature_decision.csv**
```
timestamp,feature,decision
```
Features: `EmergencyBraking` (`BRAKE` / `NO_BRAKE`), `LaneKeeping` (`CORRECTION:<value>`), `CruiseControl` (`ADJUSTMENT:<value>`)
