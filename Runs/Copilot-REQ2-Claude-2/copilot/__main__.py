"""CLI entry point for the Copilot driver-assistance system.

Usage:
    python -m copilot --input <input_dir> --output <output_dir>
"""

import argparse
import sys
import time

from .ingestion import load_events
from .state_machine import run
from .writer import flush_outputs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="copilot",
        description="Copilot autonomous driver-assistance simulation.",
    )
    parser.add_argument("--input", required=True, metavar="<dir>",
                        help="Directory containing sensor_log.csv and driver_events.csv")
    parser.add_argument("--output", required=True, metavar="<dir>",
                        help="Directory where output CSV files will be written")
    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    print(f"[Copilot] Loading events from: {args.input}")
    try:
        events = load_events(args.input)
    except FileNotFoundError as exc:
        print(f"[Copilot] ERROR – input file not found: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[Copilot] ERROR – failed to load events: {exc}", file=sys.stderr)
        return 1

    total = len(events)
    print(f"[Copilot] Loaded {total} events. Starting processing...")

    start = time.monotonic()
    ctx = run(events)
    elapsed = time.monotonic() - start

    print(f"[Copilot] Processing complete in {elapsed * 1000:.1f} ms.")
    print(f"[Copilot] State transitions : {len(ctx.state_transitions)}")
    print(f"[Copilot] Feature decisions : {len(ctx.feature_decisions)}")
    print(f"[Copilot] Actuator commands : {len(ctx.actuator_commands)}")

    print(f"[Copilot] Writing output to: {args.output}")
    try:
        flush_outputs(args.output, ctx)
    except Exception as exc:
        print(f"[Copilot] ERROR – failed to write outputs: {exc}", file=sys.stderr)
        return 1

    print("[Copilot] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
