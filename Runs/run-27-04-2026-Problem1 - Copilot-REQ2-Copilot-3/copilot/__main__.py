"""CLI entry point: `python -m copilot --input <dir> --output <dir>` (section 3.4)."""

import argparse
import sys
import time

from copilot.ingestion import load_sensor_events, load_driver_events, merge_event_stream
from copilot.output import OutputWriter
from copilot.state_machine import CopilotStateMachine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="copilot",
        description="Copilot driver-assistance system simulation",
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="<dir>",
        help="Directory containing sensor_log.csv and driver_events.csv",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="<dir>",
        help="Directory where state_log.csv, commands_log.csv, and feature_decision.csv are written",
    )
    return parser


def run(input_dir: str, output_dir: str) -> None:
    """Load inputs, process event stream, and flush outputs (PF-02)."""

    print(f"[Copilot] Loading sensor events from: {input_dir}")
    sensor_events = load_sensor_events(input_dir)
    print(f"[Copilot] Loaded {len(sensor_events)} sensor event(s).")

    print(f"[Copilot] Loading driver events from: {input_dir}")
    driver_events = load_driver_events(input_dir)
    print(f"[Copilot] Loaded {len(driver_events)} driver event(s).")

    stream = merge_event_stream(sensor_events, driver_events)
    print(f"[Copilot] Merged stream contains {len(stream)} event(s). Starting processing…")

    writer = OutputWriter(output_dir)
    machine = CopilotStateMachine(writer)

    for idx, (kind, event) in enumerate(stream, start=1):
        t_start = time.monotonic()
        machine.process_event(kind, event)
        elapsed_ms = (time.monotonic() - t_start) * 1000

        print(
            f"[Copilot] [{idx}/{len(stream)}] ts={event.timestamp:.3f} "
            f"type={kind} state={machine.state.value} ({elapsed_ms:.2f} ms)"
        )

    print(f"[Copilot] Writing output files to: {output_dir}")
    writer.flush()
    print("[Copilot] Done.")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        run(args.input, args.output)
    except FileNotFoundError as exc:
        print(f"[Copilot] ERROR – input file not found: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"[Copilot] ERROR – {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
