#!/usr/bin/env python3
"""
Copilot driver-assistance system — main entry point.

Usage:
    python main.py --input <input_dir> --output <output_dir>

The program reads *sensor_log.csv* and *driver_events.csv* from <input_dir>,
processes all events in ascending timestamp order, and writes the three output
CSV files to <output_dir>.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Union

from copilot.actuator import (
    ActuatorCommand,
    alarm_command,
    attentiveness_prompt_command,
    emergency_brake_command,
    lane_keep_command,
    speed_adjust_command,
)
from copilot.features import (
    evaluate_cruise_control,
    evaluate_emergency_braking,
    evaluate_lane_keeping,
)
from copilot.output import OutputWriter
from copilot.perception import DriverEvent, SensorEvent, load_driver_events, load_sensor_events
from copilot.state_machine import CopilotContext, State

# ---------------------------------------------------------------------------
# System-wide constants (FR-02, FR-03, FR-04)
# ---------------------------------------------------------------------------

ATTENTIVENESS_INTERVAL_S: float = 120.0   # seconds between attentiveness prompts
RESPONSE_WINDOW_S: float = 5.0            # seconds driver has to respond before alarm
OVERRIDE_FORCE_N: float = 10.0            # force (N) that triggers immediate disengage
VALID_RESPONSE_FORCE_N: float = 3.0       # maximum force (N) counted as valid response


# ---------------------------------------------------------------------------
# Formatting helper
# ---------------------------------------------------------------------------

def _hms(ts: float) -> str:
    """Format a Unix timestamp as HH:MM:SS (UTC) for console output."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# Timer-based transition checks  (FR-03)
# ---------------------------------------------------------------------------

def _check_timers(
    current_time: float,
    ctx: CopilotContext,
    writer: OutputWriter,
) -> None:
    """Fire any timer-driven state transitions that are due before *current_time*.

    Two timers are tracked:
      1. The 120-second attentiveness prompt (Engaged -> AwaitingResponse).
      2. The 5-second response window    (AwaitingResponse -> Alarming).

    Both timers use the exact expiry timestamp so that output records are
    precise even when events arrive later than the nominal expiry time.
    """
    # --- 120-second attentiveness prompt -----------------------------------
    if ctx.state == State.ENGAGED and ctx.last_prompt_time is not None:
        prompt_due = ctx.last_prompt_time + ATTENTIVENESS_INTERVAL_S
        if current_time >= prompt_due:
            _issue_attentiveness_prompt(prompt_due, ctx, writer)

    # --- 5-second response-window timeout ----------------------------------
    # Checked after the potential prompt above so a cascading timeout
    # (event arrives >125 s after last prompt with no responses) is handled
    # in a single pass.
    if ctx.state == State.AWAITING_RESPONSE and ctx.awaiting_start_time is not None:
        alarm_due = ctx.awaiting_start_time + RESPONSE_WINDOW_S
        if current_time > alarm_due:
            _trigger_alarm(alarm_due, ctx, writer)


def _issue_attentiveness_prompt(
    timestamp: float,
    ctx: CopilotContext,
    writer: OutputWriter,
) -> None:
    """Emit a steering-wheel nudge and transition from Engaged -> AwaitingResponse."""
    writer.record_command(attentiveness_prompt_command(timestamp))
    prev = ctx.state
    ctx.state = State.AWAITING_RESPONSE
    ctx.awaiting_start_time = timestamp
    writer.record_state_transition(timestamp, prev, State.AWAITING_RESPONSE, "ATTENTIVENESS_TIMER")
    print(f"  [{_hms(timestamp)}] Attentiveness prompt issued  →  AwaitingResponse")


def _trigger_alarm(
    timestamp: float,
    ctx: CopilotContext,
    writer: OutputWriter,
) -> None:
    """Emit a continuous alarm and transition from AwaitingResponse -> Alarming."""
    writer.record_command(alarm_command(timestamp))
    prev = ctx.state
    ctx.state = State.ALARMING
    ctx.awaiting_start_time = None
    writer.record_state_transition(timestamp, prev, State.ALARMING, "RESPONSE_TIMEOUT")
    print(f"  [{_hms(timestamp)}] Response timeout             →  Alarming")


# ---------------------------------------------------------------------------
# Sensor event processing  (PF-01, FR-02)
# ---------------------------------------------------------------------------

def _handle_sensor_event(
    event: SensorEvent,
    ctx: CopilotContext,
    writer: OutputWriter,
) -> None:
    """Dispatch a sensor reading to the appropriate autonomous features.

    Lidar is evaluated unconditionally (emergency braking has universal priority).
    Camera features are evaluated only in Engaged mode.
    """
    if event.sensor_type == "lidar":
        decision = evaluate_emergency_braking(event.timestamp, event.data_value)
        writer.record_decision(decision)

        if decision.decision == "BRAKE":
            # Emergency braking is always issued regardless of operating mode (FR-02).
            cmd = emergency_brake_command(event.timestamp)
            writer.record_command(cmd)
            print(
                f"  [{_hms(event.timestamp)}] EMERGENCY BRAKE"
                f"  (sensor={event.sensor_id}, distance={event.data_value} {event.unit})"
            )

    elif event.sensor_type == "camera":
        # Camera-based features are active only in Engaged mode (PF-01).
        if ctx.state != State.ENGAGED:
            return

        lk_decision = evaluate_lane_keeping(event.timestamp, event.data_value)
        cc_decision = evaluate_cruise_control(event.timestamp, event.data_value)
        writer.record_decision(lk_decision)
        writer.record_decision(cc_decision)

        writer.record_command(lane_keep_command(event.timestamp, event.data_value))
        writer.record_command(speed_adjust_command(event.timestamp, event.data_value))


# ---------------------------------------------------------------------------
# Driver event processing  (FR-01, FR-03, FR-04)
# ---------------------------------------------------------------------------

def _handle_driver_event(
    event: DriverEvent,
    ctx: CopilotContext,
    writer: OutputWriter,
) -> None:
    """Process a driver interaction and apply the corresponding state transition rules."""
    if event.event_type == "ENGAGE":
        _handle_engage(event, ctx, writer)
    elif event.event_type == "DISENGAGE":
        _handle_disengage(event, ctx, writer)
    elif event.event_type == "STEERING_FORCE":
        _handle_steering_force(event, ctx, writer)


def _handle_engage(
    event: DriverEvent,
    ctx: CopilotContext,
    writer: OutputWriter,
) -> None:
    """Transition from Disengaged to Engaged when the driver issues ENGAGE."""
    if ctx.state != State.DISENGAGED:
        return  # No state change; FR-01 says do not log non-transitions.
    prev = ctx.state
    ctx.state = State.ENGAGED
    ctx.last_prompt_time = event.timestamp   # Start the 120-second prompt timer.
    writer.record_state_transition(event.timestamp, prev, State.ENGAGED, "ENGAGE_EVENT")
    print(f"  [{_hms(event.timestamp)}] Driver engaged              →  Engaged")


def _handle_disengage(
    event: DriverEvent,
    ctx: CopilotContext,
    writer: OutputWriter,
) -> None:
    """Transition to Disengaged when the driver explicitly issues DISENGAGE."""
    if ctx.state == State.DISENGAGED:
        return  # Already disengaged; nothing to do.
    prev = ctx.state
    ctx.state = State.DISENGAGED
    ctx.last_prompt_time = None
    ctx.awaiting_start_time = None
    writer.record_state_transition(event.timestamp, prev, State.DISENGAGED, "DISENGAGE_EVENT")
    print(f"  [{_hms(event.timestamp)}] Driver disengaged           →  Disengaged")


def _handle_steering_force(
    event: DriverEvent,
    ctx: CopilotContext,
    writer: OutputWriter,
) -> None:
    """Apply steering-force rules (FR-03 response / FR-04 override).

    Force >  10 N : driver override -> Disengaged   (FR-04, any state)
    Force <= 3 N  : valid attentiveness response     (FR-03, AwaitingResponse or Alarming)
    3 N < Force <= 10 N : ignored while AwaitingResponse; no effect otherwise.
    """
    force = event.value

    if force > OVERRIDE_FORCE_N:
        # FR-04: immediate disengagement regardless of current state.
        if ctx.state == State.DISENGAGED:
            return  # No actual state change; do not log.
        prev = ctx.state
        ctx.state = State.DISENGAGED
        ctx.last_prompt_time = None
        ctx.awaiting_start_time = None
        writer.record_state_transition(event.timestamp, prev, State.DISENGAGED, "DRIVER_OVERRIDE")
        print(f"  [{_hms(event.timestamp)}] Driver override ({force} N)      →  Disengaged")
        return

    if force <= VALID_RESPONSE_FORCE_N:
        if ctx.state == State.AWAITING_RESPONSE:
            # Valid attentiveness response within the 5-second window.
            prev = ctx.state
            ctx.state = State.ENGAGED
            ctx.last_prompt_time = event.timestamp   # Reset the 120-second timer.
            ctx.awaiting_start_time = None
            writer.record_state_transition(event.timestamp, prev, State.ENGAGED, "VALID_RESPONSE")
            print(f"  [{_hms(event.timestamp)}] Valid response ({force} N)       →  Engaged")

        elif ctx.state == State.ALARMING:
            # Alarm acknowledged with a gentle force; return to Engaged.
            prev = ctx.state
            ctx.state = State.ENGAGED
            ctx.last_prompt_time = event.timestamp
            writer.record_state_transition(event.timestamp, prev, State.ENGAGED, "ALARM_CLEARED")
            print(f"  [{_hms(event.timestamp)}] Alarm cleared ({force} N)        →  Engaged")

    # Forces in (3, 10] N are silently ignored while in AwaitingResponse (FR-03).


# ---------------------------------------------------------------------------
# Main processing loop  (PF-02)
# ---------------------------------------------------------------------------

def run(input_dir: Path, output_dir: Path) -> None:
    """Load events, merge them, and process each one in ascending timestamp order."""
    sensor_path = input_dir / "sensor_log.csv"
    driver_path = input_dir / "driver_events.csv"

    print(f"Loading sensor events  from {sensor_path}")
    sensor_events = load_sensor_events(sensor_path)
    print(f"  → {len(sensor_events)} sensor event(s) loaded")

    print(f"Loading driver events  from {driver_path}")
    driver_events = load_driver_events(driver_path)
    print(f"  → {len(driver_events)} driver event(s) loaded")

    # Merge all events into a single timestamp-ordered stream (PF-02).
    all_events: List[Union[SensorEvent, DriverEvent]] = sorted(
        sensor_events + driver_events,
        key=lambda e: e.timestamp,
    )
    print(f"\nProcessing {len(all_events)} event(s) in chronological order...\n")

    ctx = CopilotContext()
    writer = OutputWriter(output_dir)

    for event in all_events:
        # Evaluate timer-driven transitions before dispatching the current event.
        _check_timers(event.timestamp, ctx, writer)

        if isinstance(event, SensorEvent):
            _handle_sensor_event(event, ctx, writer)
        else:
            _handle_driver_event(event, ctx, writer)

    writer.flush()

    print(f"\nProcessing complete.  Output written to: {output_dir}/")
    print(f"  state_log.csv        → {output_dir / 'state_log.csv'}")
    print(f"  commands_log.csv     → {output_dir / 'commands_log.csv'}")
    print(f"  feature_decision.csv → {output_dir / 'feature_decision.csv'}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="copilot",
        description="Copilot driver-assistance system — offline simulation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --input ./data --output ./out\n"
            "  copilot         --input ./data --output ./out\n"
        ),
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
        help="Directory where state_log.csv, commands_log.csv, and feature_decision.csv are written",
    )
    return parser


def main() -> None:
    """Parse CLI arguments, validate inputs, and execute the processing pipeline."""
    args = _build_parser().parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    errors: List[str] = []
    if not input_dir.is_dir():
        errors.append(f"Input directory not found: {input_dir}")
    else:
        for required in ("sensor_log.csv", "driver_events.csv"):
            if not (input_dir / required).is_file():
                errors.append(f"Required input file missing: {input_dir / required}")

    if errors:
        for msg in errors:
            print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)

    run(input_dir, output_dir)


if __name__ == "__main__":
    main()
