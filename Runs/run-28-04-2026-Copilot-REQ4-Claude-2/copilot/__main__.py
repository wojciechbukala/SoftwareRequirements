"""
CLI entry point for the Copilot ADAS simulation.

Usage:
    python -m copilot --input <input_dir> --output <output_dir>

Both arguments are mandatory.  The input directory must contain:
    sensor_log.csv    – periodic Lidar / Camera readings
    driver_events.csv – ENGAGE / DISENGAGE / STEERING_FORCE events

Results are written to the output directory:
    state_log.csv        – state-machine transitions
    commands_log.csv     – actuator commands
    feature_decision.csv – autonomous-feature decisions
"""

import argparse
import sys
import time

from .decision import CopilotEngine
from .output import write_all
from .perception import load_all_events


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="copilot",
        description="Copilot – ADAS onboard computer simulation",
    )
    parser.add_argument(
        "--input",
        metavar="DIR",
        required=True,
        help="Directory containing sensor_log.csv and driver_events.csv",
    )
    parser.add_argument(
        "--output",
        metavar="DIR",
        required=True,
        help="Directory where output CSV files will be written",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    print(f"[Copilot] Loading events from: {args.input}")
    t0 = time.perf_counter()

    try:
        events = load_all_events(args.input)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[Copilot] ERROR loading input: {exc}", file=sys.stderr)
        return 1

    print(f"[Copilot] Loaded {len(events)} event(s).")

    engine = CopilotEngine()
    state = engine.process_events(events)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(
        f"[Copilot] Simulation complete in {elapsed_ms:.1f} ms "
        f"({len(events)} events processed)."
    )
    print(
        f"[Copilot] Final state: {state.current_state.value} | "
        f"State transitions: {len(state.state_log)} | "
        f"Commands: {len(state.commands_log)} | "
        f"Feature decisions: {len(state.feature_decision_log)}"
    )

    try:
        write_all(args.output, state)
    except OSError as exc:
        print(f"[Copilot] ERROR writing output: {exc}", file=sys.stderr)
        return 1

    print(f"[Copilot] Output written to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
