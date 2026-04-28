# Copilot Implementation Summary

## What was built

A command-line Python simulation of the Copilot driver-assistance system, fully implementing all functional requirements from `REQUIREMENTS.md`.

---

## How to run

```
python3 main.py --input <input_dir> --output <output_dir>
```

`<input_dir>` must contain `sensor_log.csv` and `driver_events.csv`.  
`<output_dir>` will receive `state_log.csv`, `commands_log.csv`, and `feature_decision.csv`.

A POSIX shell wrapper `copilot_run` (executable) is also provided.

---

## File structure

```
main.py                  – CLI entry point and main processing loop (PF-02)
copilot/
  __init__.py
  perception.py          – Perception layer: CSV parsing (SensorEvent, DriverEvent)
  state_machine.py       – State definitions (State enum) and runtime context
  features.py            – Decision logic: EmergencyBraking, LaneKeeping, CruiseControl
  actuator.py            – Actuator control layer: command factories and identifiers
  output.py              – Output layer: collects records, writes CSV files
```

The three-layer separation required by §3.5 is reflected directly in the module boundaries.

---

## Requirements coverage

### FR-01 — State machine
Four states: `Disengaged` (initial), `Engaged`, `AwaitingResponse`, `Alarming`.  
Only actual state changes are written to `state_log.csv`.

### FR-02 — Autonomous driving logic
- **Lidar** events are evaluated for emergency braking *unconditionally* (all states).  
  Distance < 5 m → `BRAKE` decision + `BrakingSystem / EMERGENCY_BRAKE` command.  
  Distance ≥ 5 m → `NO_BRAKE` decision recorded.  
- **Camera** events are processed only in `Engaged` state.  
  Produces `LaneKeeping` (CORRECTION) and `CruiseControl` (ADJUSTMENT) decisions and
  corresponding `SteeringMotor` / `SpeedActuator` commands.

### FR-03 — Attentiveness monitoring
- 120-second interval (from entering Engaged) triggers an `ATTENTIVENESS_PROMPT` command to `SteeringMotor` and a transition to `AwaitingResponse`.  
- Up to 5 seconds for a valid response (force ≤ 3 N).  
  - Valid response → back to `Engaged`, timer reset.  
  - Force in (3, 10] N → silently ignored; waiting continues.  
  - Timeout → `CONTINUOUS_ALARM` to `Alarm` actuator + transition to `Alarming`.  
- Force ≤ 3 N while `Alarming` → clears alarm, returns to `Engaged`.

### FR-04 — Driver override
Force > 10 N in any state → immediate transition to `Disengaged` (trigger `DRIVER_OVERRIDE`).

### FR-05 / PF-02 — Event ingestion
All events from both input files are merged into a single timestamp-ascending stream and dispatched in order. Timer-driven transitions (attentiveness prompt, response timeout) are fired at their exact expiry timestamps before each incoming event is processed, ensuring accurate output timestamps even when events arrive late.

---

## Design decisions

| Decision | Rationale |
|---|---|
| Pure Python stdlib, no third-party packages | Satisfies portability (POSIX + Windows) and no-external-engine requirement (§3.4, §3.6) |
| Events sorted by `float` timestamp | Single-pass stable merge; handles both numeric and ISO-8601 input timestamps |
| Timer expiry at exact due-time, not event-time | Output timestamps are precise regardless of event granularity |
| Emergency braking always active | "Always" and "regardless of the current operating mode" language in FR-02 / PF-01 takes precedence over the general Disengaged-mode suppression sentence |
| Camera features only in `Engaged` | PF-01 explicitly: "the program only takes further action when it is currently in engaged mode" |
| Records flushed once at end | All records held in memory; single write pass per output file (§3.2 PF-02: "flushes all output files and terminates") |
