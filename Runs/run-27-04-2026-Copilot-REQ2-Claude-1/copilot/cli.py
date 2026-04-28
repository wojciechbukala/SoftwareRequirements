"""Command-line interface entry point for the Copilot driver-assistance system."""

import argparse
import sys
from pathlib import Path

from copilot.output import OutputWriter
from copilot.perception import load_events
from copilot.state_machine import StateMachine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="copilot",
        description="Copilot autonomous driver-assistance simulation.",
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="<dir>",
        help="Directory containing sensor_log.csv and driver_events.csv.",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="<dir>",
        help="Directory where state_log.csv, commands_log.csv, and feature_decision.csv are written.",
    )
    return parser


def run(input_dir: Path, output_dir: Path) -> None:
    """Load events, process them through the state machine, and flush output files."""
    print(f"Copilot starting.")
    print(f"  Input  : {input_dir}")
    print(f"  Output : {output_dir}")

    events = load_events(input_dir)
    print(f"  Loaded {len(events)} event(s).")

    writer = OutputWriter(output_dir)
    machine = StateMachine(writer)

    for idx, (kind, event) in enumerate(events, start=1):
        ts = event.timestamp_raw
        label = kind.upper()
        if kind == "sensor":
            detail = f"{event.sensor_type}  value={event.data_value}"  # type: ignore[union-attr]
        else:
            detail = f"{event.event_type}  value={event.value}"  # type: ignore[union-attr]
        print(f"[{idx:>4}] t={ts:<12} {label:<8} {detail}")
        machine.process_event(kind, event)

    writer.flush()
    print("Copilot finished. Output files written.")


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.is_dir():
        print(f"Error: input directory does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)

    run(input_dir, output_dir)


if __name__ == "__main__":
    main()
