"""
Copilot CLI entry point.

Usage
-----
::

    python -m copilot --input <input_dir> --output <output_dir>

The module orchestrates the full simulation pipeline (PF-02):

1. Read ``sensor_log.csv`` and ``driver_events.csv`` from *input_dir*.
2. Merge both streams into a single time-ordered event sequence.
3. For each event:
   a. Check time-based state transitions (120 s prompt, 5 s timeout).
   b. Drain any commands emitted by those transitions.
   c. Dispatch the event to the sensor or driver handler.
4. Write ``state_log.csv``, ``commands_log.csv``, and
   ``feature_decision.csv`` to *output_dir*.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from copilot.actuator import (
    ActuatorCommand,
    brake_command,
    speed_command,
    steer_command,
)
from copilot.decision import FeatureDecision, evaluate_camera, evaluate_lidar
from copilot.output import write_commands_log, write_feature_decisions, write_state_log
from copilot.perception import (
    AnyEvent,
    DriverEvent,
    SensorEvent,
    merge_events,
    read_driver_events,
    read_sensor_events,
)
from copilot.state_machine import State, StateMachine


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def _handle_sensor_event(
    event: SensorEvent,
    sm: StateMachine,
    all_commands: list[ActuatorCommand],
    all_decisions: list[FeatureDecision],
) -> None:
    """
    Dispatch a sensor event through the perception → decision → actuator chain.

    LIDAR events are always evaluated (emergency braking takes priority).
    Camera events are only evaluated when the system is in Engaged state.

    If emergency braking is triggered by a LIDAR reading, lane-keeping and
    cruise-control processing is skipped for this cycle.

    Args:
        event:         The incoming :class:`~copilot.perception.SensorEvent`.
        sm:            Live :class:`~copilot.state_machine.StateMachine`.
        all_commands:  Accumulator for :class:`~copilot.actuator.ActuatorCommand`.
        all_decisions: Accumulator for :class:`~copilot.decision.FeatureDecision`.
    """
    ts = event.timestamp

    if event.sensor_type.upper() == "LIDAR":
        decisions = evaluate_lidar(ts, event.data_value)
        all_decisions.extend(decisions)

        braking = any(d.decision == "BRAKE" for d in decisions)
        if braking:
            all_commands.append(brake_command(ts))
            # Skip lane-keeping / cruise-control this cycle as per PF-01.
            return

    elif event.sensor_type.upper() == "CAMERA":
        if sm.current_state != State.ENGAGED:
            # Camera processing only runs while Engaged.
            return

        decisions = evaluate_camera(ts, event.data_value)
        all_decisions.extend(decisions)

        # Map camera decisions to actuator commands.
        for d in decisions:
            if d.feature == "lane_keeping":
                all_commands.append(steer_command(ts, float(d.decision)))
            elif d.feature == "cruise_control":
                all_commands.append(speed_command(ts, float(d.decision)))


def _handle_driver_event(
    event: DriverEvent,
    sm: StateMachine,
) -> None:
    """
    Dispatch a driver event to the appropriate state-machine handler.

    Args:
        event: The incoming :class:`~copilot.perception.DriverEvent`.
        sm:    Live :class:`~copilot.state_machine.StateMachine`.
    """
    etype = event.event_type.upper()
    if etype == "ENGAGE":
        sm.handle_engage(event.timestamp)
    elif etype == "DISENGAGE":
        sm.handle_disengage(event.timestamp)
    elif etype == "STEERING_FORCE":
        sm.handle_steering_force(event.timestamp, event.value)


# ---------------------------------------------------------------------------
# Main event loop
# ---------------------------------------------------------------------------

def run_simulation(input_dir: Path, output_dir: Path) -> None:
    """
    Execute the full Copilot simulation pipeline.

    Args:
        input_dir:  Directory containing ``sensor_log.csv`` and
                    ``driver_events.csv``.
        output_dir: Directory where the three output CSV files will be written.
                    Created automatically if it does not exist.
    """
    # ---- Input validation ------------------------------------------------
    sensor_path = input_dir / "sensor_log.csv"
    driver_path = input_dir / "driver_events.csv"

    for p in (sensor_path, driver_path):
        if not p.exists():
            print(f"[ERROR] Required input file not found: {p}", file=sys.stderr)
            sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Step 1 & 2: Load and merge events --------------------------------
    print("[INFO] Reading sensor events …")
    sensor_events = read_sensor_events(sensor_path)
    print(f"[INFO]   {len(sensor_events)} sensor event(s) loaded.")

    print("[INFO] Reading driver events …")
    driver_events = read_driver_events(driver_path)
    print(f"[INFO]   {len(driver_events)} driver event(s) loaded.")

    print("[INFO] Merging event streams …")
    merged = merge_events(sensor_events, driver_events)
    print(f"[INFO]   {len(merged)} total event(s) in merged stream.")

    # ---- Step 3: Initialise accumulators ----------------------------------
    sm = StateMachine()
    all_commands: list[ActuatorCommand] = []
    all_decisions: list[FeatureDecision] = []

    # ---- Step 4: Event loop -----------------------------------------------
    print("[INFO] Starting event loop …")
    for idx, event in enumerate(merged, start=1):
        ts = event.timestamp

        # (a) Check time-based transitions before handling the event.
        sm.check_time_transitions(ts)

        # (b) Drain commands that may have been emitted by time transitions.
        if sm.pending_commands:
            all_commands.extend(sm.pending_commands)
            sm.pending_commands.clear()

        # (c) Dispatch to the appropriate handler.
        if isinstance(event, SensorEvent):
            _handle_sensor_event(event, sm, all_commands, all_decisions)
        elif isinstance(event, DriverEvent):
            _handle_driver_event(event, sm)

        # Real-time status update every 50 events (and for the last one).
        if idx % 50 == 0 or idx == len(merged):
            print(
                f"[INFO]   Processed {idx}/{len(merged)} events | "
                f"state={sm.current_state.value}"
            )

    print(
        f"[INFO] Event loop complete. "
        f"Final state: {sm.current_state.value} | "
        f"Transitions: {len(sm.transitions)} | "
        f"Commands: {len(all_commands)} | "
        f"Decisions: {len(all_decisions)}"
    )

    # ---- Step 5: Write outputs --------------------------------------------
    print("[INFO] Writing output files …")
    write_state_log(output_dir, sm.transitions)
    print(f"[INFO]   state_log.csv        — {len(sm.transitions)} row(s)")

    write_commands_log(output_dir, all_commands)
    print(f"[INFO]   commands_log.csv     — {len(all_commands)} row(s)")

    write_feature_decisions(output_dir, all_decisions)
    print(f"[INFO]   feature_decision.csv — {len(all_decisions)} row(s)")

    print("[INFO] Simulation finished successfully.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Construct and return the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="copilot",
        description=(
            "Copilot — driver-assistance simulation. "
            "Reads sensor_log.csv and driver_events.csv from INPUT_DIR and "
            "writes state_log.csv, commands_log.csv, and feature_decision.csv "
            "to OUTPUT_DIR."
        ),
    )
    parser.add_argument(
        "--input",
        metavar="INPUT_DIR",
        required=True,
        help="Directory containing sensor_log.csv and driver_events.csv.",
    )
    parser.add_argument(
        "--output",
        metavar="OUTPUT_DIR",
        required=True,
        help="Directory where output CSV files will be written.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """
    Parse CLI arguments and run the simulation.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]`` when *None*).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    if not input_dir.is_dir():
        print(f"[ERROR] Input directory does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)

    run_simulation(input_dir, output_dir)


if __name__ == "__main__":
    main()
