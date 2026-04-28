"""Actuator layer: writes simulation results to output CSV files."""
import csv
from pathlib import Path
from typing import List

from models import CommandEntry, FeatureDecisionEntry, StateLogEntry


def write_state_log(output_dir: Path, entries: List[StateLogEntry]) -> None:
    """Write state_log.csv — one row per state transition."""
    path = output_dir / "state_log.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
        for entry in entries:
            writer.writerow([
                entry.timestamp,
                entry.previous_state.value,
                entry.current_state.value,
                entry.trigger_event,
            ])


def write_commands_log(output_dir: Path, entries: List[CommandEntry]) -> None:
    """Write commands_log.csv — one row per actuator command."""
    path = output_dir / "commands_log.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "actuator_id", "values"])
        for entry in entries:
            writer.writerow([
                entry.timestamp,
                entry.actuator_id.value,
                entry.values,
            ])


def write_feature_decisions(output_dir: Path, entries: List[FeatureDecisionEntry]) -> None:
    """Write feature_decision.csv — one row per feature-level decision."""
    path = output_dir / "feature_decision.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "feature", "decision"])
        for entry in entries:
            writer.writerow([
                entry.timestamp,
                entry.feature.value,
                entry.decision.value,
            ])
