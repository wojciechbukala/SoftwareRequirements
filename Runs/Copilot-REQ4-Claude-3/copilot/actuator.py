"""
Actuator control layer: output record types and CSV writers.

Defines the data structures emitted by the decision layer and provides
functions to serialise them to the required CSV output files.
"""

import csv
from dataclasses import dataclass
from typing import List


@dataclass
class StateLogEntry:
    """One recorded state transition."""

    timestamp: float
    previous_state: str
    current_state: str
    trigger_event: str  # human-readable label for what caused the transition


@dataclass
class CommandEntry:
    """One actuator command emitted by the system."""

    timestamp: float
    actuator_id: str  # BrakingSystem | SteeringMotor | SpeedActuator | AlarmActuator
    values: str       # command payload (e.g. BRAKE, ADJUST, PROMPT, ALARM)


@dataclass
class FeatureDecisionEntry:
    """One feature-level decision record."""

    timestamp: float
    feature: str    # EmergencyBraking | LaneKeeping | CruiseControl
    decision: str   # BRAKE | NO_BRAKE | ADJUST


def write_state_log(entries: List[StateLogEntry], path: str) -> None:
    """Write *state_log.csv* to *path*."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
        for e in entries:
            writer.writerow([e.timestamp, e.previous_state, e.current_state, e.trigger_event])


def write_commands_log(entries: List[CommandEntry], path: str) -> None:
    """Write *commands_log.csv* to *path*."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "actuator_id", "values"])
        for e in entries:
            writer.writerow([e.timestamp, e.actuator_id, e.values])


def write_feature_decisions(entries: List[FeatureDecisionEntry], path: str) -> None:
    """Write *feature_decision.csv* to *path*."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "feature", "decision"])
        for e in entries:
            writer.writerow([e.timestamp, e.feature, e.decision])
