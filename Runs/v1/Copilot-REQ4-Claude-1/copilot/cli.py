"""Command-line interface for the Copilot ADAS simulation."""

import argparse
import sys
from pathlib import Path

from .engine import SimulationEngine
from .parser import parse_driver_events, parse_sensor_log
from .writer import write_commands_log, write_feature_decisions, write_state_log


def main() -> None:
    """
    Entry point: parse arguments, run simulation, write outputs.

    Usage::

        copilot --input <dir> --output <dir>
    """
    args = _build_parser().parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.is_dir():
        print(f"[Copilot] ERROR: input directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Perception layer – load inputs                                       #
    # ------------------------------------------------------------------ #
    sensor_path = input_dir / "sensor_log.csv"
    driver_path = input_dir / "driver_events.csv"

    print(f"[Copilot] Reading sensor log    : {sensor_path}")
    sensor_events = parse_sensor_log(sensor_path)
    print(f"[Copilot] Loaded {len(sensor_events)} sensor event(s).")

    print(f"[Copilot] Reading driver events : {driver_path}")
    driver_events = parse_driver_events(driver_path)
    print(f"[Copilot] Loaded {len(driver_events)} driver event(s).")

    # ------------------------------------------------------------------ #
    # Decision layer – run state-machine simulation                        #
    # ------------------------------------------------------------------ #
    print("[Copilot] Running simulation ...")
    engine = SimulationEngine()
    engine.run(sensor_events + driver_events)

    print(
        f"[Copilot] Simulation complete – "
        f"{len(engine.state_log)} state transition(s), "
        f"{len(engine.commands_log)} command(s), "
        f"{len(engine.feature_decisions)} feature decision(s)."
    )

    # ------------------------------------------------------------------ #
    # Actuator control layer – write outputs                               #
    # ------------------------------------------------------------------ #
    state_out = output_dir / "state_log.csv"
    cmd_out = output_dir / "commands_log.csv"
    dec_out = output_dir / "feature_decision.csv"

    print(f"[Copilot] Writing state_log        → {state_out}")
    write_state_log(state_out, engine.state_log)

    print(f"[Copilot] Writing commands_log     → {cmd_out}")
    write_commands_log(cmd_out, engine.commands_log)

    print(f"[Copilot] Writing feature_decision → {dec_out}")
    write_feature_decisions(dec_out, engine.feature_decisions)

    print("[Copilot] Done.")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="copilot",
        description="Copilot ADAS – offline autonomous-driving simulation.",
    )
    p.add_argument(
        "--input", required=True, metavar="<dir>",
        help="Directory containing sensor_log.csv and driver_events.csv",
    )
    p.add_argument(
        "--output", required=True, metavar="<dir>",
        help="Directory to write state_log.csv, commands_log.csv, feature_decision.csv",
    )
    return p
