#!/usr/bin/env python3
"""
Copilot driver-assistance system simulation.

Processes sensor and driver events to maintain autonomous driving state,
issue actuator commands, and log all decisions and state transitions.
"""

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Union

# ── Constants ─────────────────────────────────────────────────────────────────

ATTENTIVENESS_INTERVAL_S: float = 120.0
"""Seconds between attentiveness prompts while Engaged."""

RESPONSE_TIMEOUT_S: float = 5.0
"""Seconds the driver has to respond to an attentiveness prompt."""

OVERRIDE_FORCE_N: float = 10.0
"""Steering force strictly above this value triggers driver override."""

VALID_RESPONSE_MAX_N: float = 3.0
"""Steering force at or below this value is a valid attentiveness response."""

EMERGENCY_BRAKE_DISTANCE_M: float = 5.0
"""Lidar distance strictly below this value triggers emergency braking."""

# Actuator identifiers
ACTUATOR_BRAKE = "BrakingSystem"
ACTUATOR_STEERING = "SteeringMotor"
ACTUATOR_SPEED = "SpeedActuator"
ACTUATOR_ALARM = "AlarmActuator"
ACTUATOR_WHEEL = "SteeringWheel"

# Feature names
FEATURE_EMERGENCY_BRAKING = "EmergencyBraking"
FEATURE_LANE_KEEPING = "LaneKeeping"
FEATURE_CRUISE_CONTROL = "CruiseControl"


# ── State Model ───────────────────────────────────────────────────────────────

class State(str, Enum):
    """Operating modes of the Copilot system."""
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class SensorEvent:
    """A single reading from an on-board sensor."""
    timestamp: float
    sensor_id: str
    sensor_type: str
    data_value: float
    unit: str


@dataclass
class DriverEvent:
    """A single interaction originating from the driver."""
    timestamp: float
    event_type: str
    value: float


AnyEvent = Union[SensorEvent, DriverEvent]


# ── Perception Layer ──────────────────────────────────────────────────────────

def parse_sensor_log(path: str) -> List[SensorEvent]:
    """Read and parse sensor_log.csv into a list of SensorEvent objects."""
    events: List[SensorEvent] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            events.append(SensorEvent(
                timestamp=float(row["timestamp"]),
                sensor_id=row["sensor_id"],
                sensor_type=row["sensor_type"],
                data_value=float(row["data_value"]),
                unit=row["unit"],
            ))
    return events


def parse_driver_events(path: str) -> List[DriverEvent]:
    """Read and parse driver_events.csv into a list of DriverEvent objects."""
    events: List[DriverEvent] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            events.append(DriverEvent(
                timestamp=float(row["timestamp"]),
                event_type=row["event_type"],
                value=float(row["value"]),
            ))
    return events


def merge_events(sensor_events: List[SensorEvent], driver_events: List[DriverEvent]) -> List[AnyEvent]:
    """
    Merge sensor and driver events into a single list ordered by ascending timestamp.
    Driver events are ordered after sensor events when timestamps are equal.
    """
    tagged = (
        [(e.timestamp, 0, e) for e in sensor_events] +
        [(e.timestamp, 1, e) for e in driver_events]
    )
    tagged.sort(key=lambda t: (t[0], t[1]))
    return [e for _, _, e in tagged]


# ── Output / Actuator Layer ───────────────────────────────────────────────────

class OutputWriter:
    """
    Collects state transitions, actuator commands, and feature decisions,
    then writes them to the appropriate CSV output files on flush.
    """

    _STATE_HEADER = ["timestamp", "previous_state", "current_state", "trigger_event"]
    _COMMANDS_HEADER = ["timestamp", "actuator_id", "values"]
    _DECISIONS_HEADER = ["timestamp", "feature", "decision"]

    def __init__(self, output_dir: str) -> None:
        self._output_dir = output_dir
        self._state_rows: list = []
        self._command_rows: list = []
        self._decision_rows: list = []

    def record_state_transition(
        self, timestamp: float, previous: State, current: State, trigger: str
    ) -> None:
        """Append one row to state_log.csv buffer."""
        self._state_rows.append((timestamp, previous.value, current.value, trigger))

    def record_command(self, timestamp: float, actuator_id: str, values: str) -> None:
        """Append one row to commands_log.csv buffer."""
        self._command_rows.append((timestamp, actuator_id, values))

    def record_feature_decision(self, timestamp: float, feature: str, decision: str) -> None:
        """Append one row to feature_decision.csv buffer."""
        self._decision_rows.append((timestamp, feature, decision))

    def flush(self) -> None:
        """Write all buffered rows to disk."""
        self._write_csv("state_log.csv", self._STATE_HEADER, self._state_rows)
        self._write_csv("commands_log.csv", self._COMMANDS_HEADER, self._command_rows)
        self._write_csv("feature_decision.csv", self._DECISIONS_HEADER, self._decision_rows)

    def _write_csv(self, filename: str, header: List[str], rows: list) -> None:
        path = os.path.join(self._output_dir, filename)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)


# ── Decision / Control Logic ──────────────────────────────────────────────────

class CopilotContext:
    """Mutable runtime context for the Copilot system."""

    def __init__(self) -> None:
        self.state: State = State.DISENGAGED
        # Timestamp when Engaged was last entered (used for 120s prompt timer).
        self.engaged_since: Optional[float] = None
        # Timestamp when AwaitingResponse was entered (used for 5s timeout).
        self.awaiting_since: Optional[float] = None


def _transition(
    ctx: CopilotContext,
    new_state: State,
    timestamp: float,
    trigger: str,
    writer: OutputWriter,
) -> None:
    """
    Change state and record the transition.  No-ops if the state does not change
    (FR-01 requires only actual changes to appear in state_log.csv).
    """
    if ctx.state == new_state:
        return
    print(f"  [{timestamp:.3f}] {ctx.state.value} → {new_state.value}  (trigger: {trigger})")
    writer.record_state_transition(timestamp, ctx.state, new_state, trigger)
    ctx.state = new_state


def _enter_engaged(ctx: CopilotContext, timestamp: float, trigger: str, writer: OutputWriter) -> None:
    """Transition to Engaged and reset the attentiveness timer."""
    _transition(ctx, State.ENGAGED, timestamp, trigger, writer)
    ctx.engaged_since = timestamp
    ctx.awaiting_since = None


def _enter_disengaged(ctx: CopilotContext, timestamp: float, trigger: str, writer: OutputWriter) -> None:
    """Transition to Disengaged and clear all timers."""
    _transition(ctx, State.DISENGAGED, timestamp, trigger, writer)
    ctx.engaged_since = None
    ctx.awaiting_since = None


def _check_time_based_transitions(
    timestamp: float, ctx: CopilotContext, writer: OutputWriter
) -> None:
    """
    Evaluate elapsed-time rules before processing the current event.

    - In AwaitingResponse: if 5 s have elapsed since the prompt, → Alarming.
    - In Engaged: if 120 s have elapsed since last prompt, issue prompt → AwaitingResponse.
    """
    if ctx.state == State.AWAITING_RESPONSE:
        if ctx.awaiting_since is not None and (timestamp - ctx.awaiting_since) > RESPONSE_TIMEOUT_S:
            _transition(ctx, State.ALARMING, timestamp, "RESPONSE_TIMEOUT", writer)
            writer.record_command(timestamp, ACTUATOR_ALARM, "CONTINUOUS_ALARM")
            ctx.awaiting_since = None

    elif ctx.state == State.ENGAGED:
        if ctx.engaged_since is not None and (timestamp - ctx.engaged_since) >= ATTENTIVENESS_INTERVAL_S:
            # Issue attentiveness prompt then move to AwaitingResponse.
            writer.record_command(timestamp, ACTUATOR_WHEEL, "ATTENTIVENESS_PROMPT")
            _transition(ctx, State.AWAITING_RESPONSE, timestamp, "ATTENTIVENESS_PROMPT", writer)
            ctx.awaiting_since = timestamp
            ctx.engaged_since = None


def _handle_lidar(event: SensorEvent, ctx: CopilotContext, writer: OutputWriter) -> bool:
    """
    Evaluate emergency braking for a Lidar reading (always active, any mode).

    Returns True if emergency braking was triggered so that the caller can
    skip further feature evaluation for this cycle.
    """
    if event.data_value < EMERGENCY_BRAKE_DISTANCE_M:
        writer.record_feature_decision(event.timestamp, FEATURE_EMERGENCY_BRAKING, "BRAKE")
        writer.record_command(event.timestamp, ACTUATOR_BRAKE, "EMERGENCY_BRAKE")
        return True
    writer.record_feature_decision(event.timestamp, FEATURE_EMERGENCY_BRAKING, "NO_BRAKE")
    return False


def _handle_camera(event: SensorEvent, writer: OutputWriter) -> None:
    """
    Compute lane-keeping correction and cruise-control adjustment from a
    camera reading and issue the corresponding commands (Engaged mode only).
    """
    correction = event.data_value   # data_value encodes the lateral offset / speed delta
    writer.record_feature_decision(event.timestamp, FEATURE_LANE_KEEPING, str(correction))
    writer.record_command(event.timestamp, ACTUATOR_STEERING, str(correction))

    writer.record_feature_decision(event.timestamp, FEATURE_CRUISE_CONTROL, str(correction))
    writer.record_command(event.timestamp, ACTUATOR_SPEED, str(correction))


def handle_sensor_event(event: SensorEvent, ctx: CopilotContext, writer: OutputWriter) -> None:
    """
    Dispatch a sensor event according to PF-01.

    Lidar emergency-braking is evaluated regardless of operating mode.
    Camera features are only evaluated when Engaged.
    """
    sensor_lower = event.sensor_type.lower()

    if sensor_lower == "lidar":
        braking_triggered = _handle_lidar(event, ctx, writer)
        if braking_triggered:
            return  # Abandon further feature evaluation for this cycle.

    if sensor_lower == "camera" and ctx.state == State.ENGAGED:
        _handle_camera(event, writer)


def handle_driver_event(event: DriverEvent, ctx: CopilotContext, writer: OutputWriter) -> None:
    """
    Dispatch a driver event according to FR-01, FR-03, and FR-04.

    Processing order:
    1. Steering-force override check (> 10 N) — always evaluated first.
    2. ENGAGE / DISENGAGE commands.
    3. Steering-force attentiveness / alarm-escape handling.
    """
    et = event.event_type
    val = event.value

    # FR-04: Any steering force > 10 N overrides to Disengaged regardless of state.
    if et == "STEERING_FORCE" and val > OVERRIDE_FORCE_N:
        _enter_disengaged(ctx, event.timestamp, "DRIVER_OVERRIDE", writer)
        return

    if et == "ENGAGE":
        if ctx.state == State.DISENGAGED:
            _enter_engaged(ctx, event.timestamp, "ENGAGE", writer)
        return

    if et == "DISENGAGE":
        if ctx.state != State.DISENGAGED:
            _enter_disengaged(ctx, event.timestamp, "DISENGAGE", writer)
        return

    if et == "STEERING_FORCE":
        if ctx.state == State.AWAITING_RESPONSE:
            if val <= VALID_RESPONSE_MAX_N:
                # Valid response — resume autonomous operation and reset prompt timer.
                _enter_engaged(ctx, event.timestamp, "VALID_RESPONSE", writer)
            # Forces in (3, 10] are explicitly ignored while awaiting response.

        elif ctx.state == State.ALARMING:
            if val <= VALID_RESPONSE_MAX_N:
                _enter_engaged(ctx, event.timestamp, "VALID_RESPONSE", writer)


# ── Main Processing Loop ──────────────────────────────────────────────────────

def run(input_dir: str, output_dir: str) -> None:
    """
    Full processing pipeline: ingest → merge → process → flush.

    Reads sensor_log.csv and driver_events.csv from input_dir, processes all
    events in ascending timestamp order, and writes the three output CSV files
    to output_dir.
    """
    sensor_path = os.path.join(input_dir, "sensor_log.csv")
    driver_path = os.path.join(input_dir, "driver_events.csv")

    print(f"Loading sensor events from:  {sensor_path}")
    sensor_events = parse_sensor_log(sensor_path)
    print(f"  {len(sensor_events)} event(s) loaded.")

    print(f"Loading driver events from:  {driver_path}")
    driver_events = parse_driver_events(driver_path)
    print(f"  {len(driver_events)} event(s) loaded.")

    events = merge_events(sensor_events, driver_events)
    print(f"Processing {len(events)} merged event(s)...")

    ctx = CopilotContext()
    writer = OutputWriter(output_dir)

    for event in events:
        _check_time_based_transitions(event.timestamp, ctx, writer)

        if isinstance(event, SensorEvent):
            print(
                f"  [{event.timestamp:.3f}] SENSOR  {event.sensor_type:<8} "
                f"id={event.sensor_id}  val={event.data_value} {event.unit}"
            )
            handle_sensor_event(event, ctx, writer)
        else:
            print(
                f"  [{event.timestamp:.3f}] DRIVER  {event.event_type:<16} val={event.value}"
            )
            handle_driver_event(event, ctx, writer)

    os.makedirs(output_dir, exist_ok=True)
    writer.flush()
    print(f"Output written to: {output_dir}")


# ── Entry Point ───────────────────────────────────────────────────────────────

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Copilot driver-assistance system simulation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input", required=True, metavar="DIR",
        help="Directory containing sensor_log.csv and driver_events.csv.",
    )
    parser.add_argument(
        "--output", required=True, metavar="DIR",
        help="Directory where state_log.csv, commands_log.csv, and feature_decision.csv will be written.",
    )
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    run(input_dir=args.input, output_dir=args.output)


if __name__ == "__main__":
    main()
