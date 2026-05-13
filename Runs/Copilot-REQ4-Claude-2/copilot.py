#!/usr/bin/env python3
"""
Copilot — Advanced Driver Assistance System Simulation

Processes sensor and driver event CSV files to simulate autonomous vehicle
safety features: lane keeping, cruise control, and emergency braking.

Usage:
    copilot --input <dir> --output <dir>
"""

import argparse
import os
import sys
import time

from perception import read_sensor_log, read_driver_events
from decision import CopilotEngine
from actuator import write_state_log, write_commands_log, write_feature_decisions


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='copilot',
        description='Copilot ADAS simulation — processes sensor and driver events.',
    )
    parser.add_argument(
        '--input', required=True, metavar='DIR',
        help='Directory containing sensor_log.csv and driver_events.csv',
    )
    parser.add_argument(
        '--output', required=True, metavar='DIR',
        help='Directory for state_log.csv, commands_log.csv, feature_decision.csv',
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    input_dir = args.input
    output_dir = args.output

    if not os.path.isdir(input_dir):
        print(f"[Copilot] ERROR: input directory '{input_dir}' not found.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    # --- Perception layer: read inputs ---
    sensor_path = os.path.join(input_dir, 'sensor_log.csv')
    driver_path = os.path.join(input_dir, 'driver_events.csv')

    print(f"[Copilot] Reading sensor log  : {sensor_path}")
    sensor_events = read_sensor_log(sensor_path)
    print(f"[Copilot]   -> {len(sensor_events)} sensor event(s) loaded.")

    print(f"[Copilot] Reading driver events: {driver_path}")
    driver_events = read_driver_events(driver_path)
    print(f"[Copilot]   -> {len(driver_events)} driver event(s) loaded.")

    all_events = sensor_events + driver_events
    print(f"[Copilot] Total events to process: {len(all_events)}")

    # --- Decision layer: run state machine ---
    print("[Copilot] Running simulation ...")
    t0 = time.monotonic()

    engine = CopilotEngine()
    engine.process(all_events)

    elapsed_ms = (time.monotonic() - t0) * 1_000
    print(f"[Copilot] Simulation complete in {elapsed_ms:.2f} ms.")
    print(f"[Copilot]   State transitions : {len(engine.state_log)}")
    print(f"[Copilot]   Commands issued   : {len(engine.commands_log)}")
    print(f"[Copilot]   Feature decisions : {len(engine.feature_decisions)}")

    # --- Actuator layer: write outputs ---
    state_path    = os.path.join(output_dir, 'state_log.csv')
    commands_path = os.path.join(output_dir, 'commands_log.csv')
    features_path = os.path.join(output_dir, 'feature_decision.csv')

    print(f"[Copilot] Writing state log      -> {state_path}")
    write_state_log(state_path, engine.state_log)

    print(f"[Copilot] Writing commands log   -> {commands_path}")
    write_commands_log(commands_path, engine.commands_log)

    print(f"[Copilot] Writing feature decisions -> {features_path}")
    write_feature_decisions(features_path, engine.feature_decisions)

    print("[Copilot] Done.")


if __name__ == '__main__':
    main()
