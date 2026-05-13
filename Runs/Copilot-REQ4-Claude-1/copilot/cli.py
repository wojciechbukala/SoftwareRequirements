"""Command-line interface and top-level orchestration."""

import argparse
import sys
import time
from pathlib import Path
from typing import List, Union

from .io_utils import (
    load_driver_events,
    write_commands_log,
    write_feature_decisions,
    write_state_log,
)
from .models import DriverEvent, SensorEvent
from .perception import load_sensor_events
from .simulation import Simulation


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="copilot",
        description="Copilot – ADAS onboard computer simulation",
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
        help="Directory where state_log.csv, commands_log.csv and "
             "feature_decision.csv will be written",
    )
    return parser


def _print_status(msg: str) -> None:
    """Print a real-time status line to stdout."""
    print(f"[copilot] {msg}", flush=True)


def main(argv: List[str] | None = None) -> int:
    """Entry point; returns an exit code (0 = success, non-zero = error)."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    # ── Validate paths ────────────────────────────────────────────────────────
    if not input_dir.is_dir():
        print(f"[copilot] ERROR: input directory not found: {input_dir}", file=sys.stderr)
        return 1

    sensor_path = input_dir / "sensor_log.csv"
    driver_path = input_dir / "driver_events.csv"

    for p in (sensor_path, driver_path):
        if not p.is_file():
            print(f"[copilot] ERROR: required input file not found: {p}", file=sys.stderr)
            return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load inputs ───────────────────────────────────────────────────────────
    _print_status(f"Loading sensor events from  {sensor_path}")
    sensor_events: List[SensorEvent] = load_sensor_events(sensor_path)
    _print_status(f"  → {len(sensor_events)} sensor event(s) loaded")

    _print_status(f"Loading driver events from  {driver_path}")
    driver_events: List[DriverEvent] = load_driver_events(driver_path)
    _print_status(f"  → {len(driver_events)} driver event(s) loaded")

    all_events: List[Union[SensorEvent, DriverEvent]] = sensor_events + driver_events
    _print_status(f"Total events to process: {len(all_events)}")

    # ── Run simulation ────────────────────────────────────────────────────────
    _print_status("Starting simulation …")
    t0 = time.perf_counter()

    sim = Simulation()
    sim.run(all_events)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    _print_status(f"Simulation complete in {elapsed_ms:.2f} ms")

    # ── Write outputs ─────────────────────────────────────────────────────────
    state_out = output_dir / "state_log.csv"
    commands_out = output_dir / "commands_log.csv"
    decisions_out = output_dir / "feature_decision.csv"

    _print_status(f"Writing state log       → {state_out}")
    write_state_log(sim.state_log, state_out)
    _print_status(f"  → {len(sim.state_log)} transition(s) recorded")

    _print_status(f"Writing commands log    → {commands_out}")
    write_commands_log(sim.commands_log, commands_out)
    _print_status(f"  → {len(sim.commands_log)} command(s) emitted")

    _print_status(f"Writing feature decisions → {decisions_out}")
    write_feature_decisions(sim.feature_decisions, decisions_out)
    _print_status(f"  → {len(sim.feature_decisions)} decision(s) recorded")

    _print_status("Done.")
    return 0
