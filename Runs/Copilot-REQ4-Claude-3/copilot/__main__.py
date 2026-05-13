"""
CLI entry point for the Copilot ADAS simulation.

Usage
─────
    python -m copilot --input <input_dir> --output <output_dir>

Both arguments are mandatory.

*input_dir* must contain:
    sensor_log.csv      – periodic Lidar and Camera readings
    driver_events.csv   – ENGAGE / DISENGAGE / STEERING_FORCE events

*output_dir* will be created if it does not exist and will receive:
    state_log.csv       – recorded state transitions
    commands_log.csv    – actuator commands emitted during the run
    feature_decision.csv – per-feature autonomous decisions
"""

import argparse
import os
import sys

from .actuator import write_commands_log, write_feature_decisions, write_state_log
from .decision import CopilotStateMachine
from .perception import load_driver_events, load_sensor_events, merge_and_sort_events


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="copilot",
        description="Copilot ADAS simulation — processes sensor and driver event logs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="DIR",
        help="Directory containing sensor_log.csv and driver_events.csv",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="DIR",
        help="Directory where output CSV files will be written",
    )
    return parser


def main() -> int:
    """Run the Copilot simulation. Returns 0 on success, non-zero on error."""
    parser = _build_parser()
    args = parser.parse_args()

    input_dir: str = args.input
    output_dir: str = args.output

    # ── Validate inputs ───────────────────────────────────────────────────────
    if not os.path.isdir(input_dir):
        print(f"[Copilot] ERROR: input directory not found: {input_dir!r}", file=sys.stderr)
        return 1

    sensor_path = os.path.join(input_dir, "sensor_log.csv")
    driver_path = os.path.join(input_dir, "driver_events.csv")

    for p in (sensor_path, driver_path):
        if not os.path.isfile(p):
            print(f"[Copilot] ERROR: required input file not found: {p!r}", file=sys.stderr)
            return 1

    # ── Perception layer: load and merge events ───────────────────────────────
    print(f"[Copilot] Loading inputs from: {input_dir}")
    try:
        sensor_events = load_sensor_events(sensor_path)
        driver_events = load_driver_events(driver_path)
    except (ValueError, KeyError) as exc:
        print(f"[Copilot] ERROR parsing input files: {exc}", file=sys.stderr)
        return 1

    all_events = merge_and_sort_events(sensor_events, driver_events)
    print(
        f"[Copilot] Loaded {len(sensor_events)} sensor event(s), "
        f"{len(driver_events)} driver event(s)  ({len(all_events)} total)"
    )

    # ── Decision layer: run simulation ────────────────────────────────────────
    machine = CopilotStateMachine()
    print("[Copilot] Starting simulation …")

    for event in all_events:
        machine.process_event(event)
        print(
            f"[Copilot]   t={event.timestamp:<10.3f}  "
            f"state={machine.state.value}"
        )

    print(
        f"[Copilot] Simulation complete.  "
        f"Final state: {machine.state.value}"
    )

    # ── Actuator layer: write outputs ─────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)
    print(f"[Copilot] Writing outputs to: {output_dir}")

    write_state_log(machine.state_log, os.path.join(output_dir, "state_log.csv"))
    write_commands_log(machine.commands_log, os.path.join(output_dir, "commands_log.csv"))
    write_feature_decisions(
        machine.feature_decisions, os.path.join(output_dir, "feature_decision.csv")
    )

    print(
        f"[Copilot] Done.  "
        f"Transitions: {len(machine.state_log)}  |  "
        f"Commands: {len(machine.commands_log)}  |  "
        f"Decisions: {len(machine.feature_decisions)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
