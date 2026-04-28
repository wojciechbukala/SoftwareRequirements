# Copilot ADAS Simulation – Implementation Summary

## What was built

A Python implementation of the Copilot onboard-computer simulation, faithful to the Alloy model in `REQUIREMENTS.md`.  The system reads CSV input, runs a discrete-time state machine, and writes CSV output.

---

## Repository layout

```
main.py                 Thin entry-point; delegates to copilot.cli.main()
copilot/
  __init__.py
  models.py             Domain enumerations and dataclasses (State, Actuator, …)
  parser.py             Perception layer – CSV input parsing
  engine.py             Decision layer – state machine (SimulationEngine)
  writer.py             Actuator control layer – CSV output serialisation
  cli.py                CLI argument parsing and orchestration
tests/
  test_engine.py        23 unit tests covering all Alloy scenarios & assertions
pyproject.toml          Package metadata and `copilot` entry-point declaration
```

---

## Usage

```bash
python main.py --input <dir> --output <dir>
# or, after pip install -e .
copilot --input <dir> --output <dir>
```

Both `--input` and `--output` are mandatory.  The tool prints real-time status to stdout.

**Input files** (inside `<dir>`):

| File | Columns |
|---|---|
| `sensor_log.csv` | timestamp, sensor_id, sensor_type, data_value, unit |
| `driver_events.csv` | timestamp, event_type, value |

**Output files** (written to `<dir>`):

| File | Columns |
|---|---|
| `state_log.csv` | timestamp, previous_state, current_state, trigger_event |
| `commands_log.csv` | timestamp, actuator_id, values |
| `feature_decision.csv` | timestamp, feature, decision |

---

## State machine

States and transitions exactly mirror the Alloy model:

```
Disengaged ──[ENGAGE]──────────────────────────────► Engaged
Engaged    ──[120 ticks without response]──────────► AwaitingResponse  (+SteeringMotor prompt)
AwaitingResponse ──[5 ticks with no response]──────► Alarming          (+AlarmActuator command)
Alarming   ──[force ≤ 3 N]────────────────────────► Engaged           (alarm escape)
Any active ──[DISENGAGE | force > 10 N]────────────► Disengaged        (override / manual)
AwaitingResponse ──[force ≤ 3 N]──────────────────► Engaged           (valid response)
```

### Constants (from Alloy model)

| Constant | Value | Meaning |
|---|---|---|
| `LIDAR_DANGER` | 5 | Obstacle distance threshold for emergency braking |
| `OVERRIDE_FORCE` | 10 N | Steering force that forces disengagement |
| `VALID_RESPONSE_FORCE` | 3 N | Max force accepted as attentiveness confirmation |
| `PROMPT_INTERVAL` | 120 ticks | Engagement duration before attentiveness check |
| `RESPONSE_WINDOW` | 5 ticks | Time allowed for driver to respond to prompt |

---

## Architecture

The implementation separates the three layers mandated by §3.2:

1. **Perception** (`parser.py`) – reads raw CSV rows, constructs typed `SensorEvent` / `DriverEvent` objects.
2. **Decision** (`engine.py`) – pure state machine; no I/O.  `SimulationEngine.run()` processes events in timestamp order and fires time-based internal transitions in the gaps between events using an O(1) jump-to-next-interesting-tick strategy (O(gap) only during `Alarming` alarm ticks).
3. **Actuator control** (`writer.py`) – serialises output buffers to UTF-8 CSV.

---

## Alloy scenario verification (smoke test outputs)

Given `ENGAGE` at t=1, a `Camera` reading at t=2, a dangerous `Lidar` at t=5, another `Camera` at t=10, an attentiveness response (`STEERING_FORCE 2 N`) at t=130, and `DISENGAGE` at t=300:

```
state_log:
  1   Disengaged → Engaged           ENGAGE
  121 Engaged → AwaitingResponse     ATTENTIVENESS_CHECK
  126 AwaitingResponse → Alarming    RESPONSE_TIMEOUT
  130 Alarming → Engaged             STEERING_FORCE (alarm escape)
  250 Engaged → AwaitingResponse     ATTENTIVENESS_CHECK
  255 AwaitingResponse → Alarming    RESPONSE_TIMEOUT
  300 Alarming → Disengaged          DISENGAGE

feature_decision:
  2   LaneKeeping    ADJUST
  2   CruiseControl  ADJUST
  5   EmergencyBraking BRAKE
  10  LaneKeeping    ADJUST
  10  CruiseControl  ADJUST
  200 EmergencyBraking NO_BRAKE
```

---

## Testing

```bash
python3 tests/test_engine.py
```

23 unit tests covering all four Alloy run scenarios and all three Alloy assertions:

- `OverrideAlwaysDisengages`
- `BrakeDecisionImpliesBrakeCommand`
- `AlarmingPrecededByAwaiting`

All tests pass (no external test framework required).

---

## Non-functional properties

- **No external dependencies** – standard library only (`csv`, `argparse`, `pathlib`, `enum`, `dataclasses`).
- **Portability** – POSIX and Windows compatible; Python ≥ 3.9.
- **Performance** – each event is processed in O(1) time; internal ticks are O(gap) only while `Alarming`.  Well within the 50 ms per-event budget on the reference machine.
- **Offline** – no network access; all I/O is local file-system only.
