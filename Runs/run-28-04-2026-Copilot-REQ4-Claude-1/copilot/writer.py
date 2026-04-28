"""Actuator control layer: serialise simulation outputs to CSV files."""

import csv
from pathlib import Path
from typing import List

from .models import CommandEntry, FeatureDecisionEntry, StateLogEntry


def write_state_log(path: Path, entries: List[StateLogEntry]) -> None:
    """Write *state_log.csv* – one row per state transition."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
        for e in entries:
            writer.writerow([e.timestamp, e.previous_state.value,
                             e.current_state.value, e.trigger_event])


def write_commands_log(path: Path, entries: List[CommandEntry]) -> None:
    """Write *commands_log.csv* – one row per actuator command."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "actuator_id", "values"])
        for e in entries:
            writer.writerow([e.timestamp, e.actuator_id.value, e.values])


def write_feature_decisions(path: Path, entries: List[FeatureDecisionEntry]) -> None:
    """Write *feature_decision.csv* – one row per feature decision."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "feature", "decision"])
        for e in entries:
            writer.writerow([e.timestamp, e.feature.value, e.decision.value])
