"""
Output (control) layer – serialises simulation results to CSV files.

Each output file corresponds to one log stored inside :class:`SystemState`:
- state_log.csv       – state-machine transitions
- commands_log.csv    – actuator commands issued
- feature_decision.csv – autonomous-feature decisions
"""

import csv
import os

from .models import SystemState


def write_state_log(output_dir: str, state: SystemState) -> None:
    """Write *state_log.csv*."""
    path = os.path.join(output_dir, "state_log.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
        for entry in state.state_log:
            writer.writerow([
                entry.timestamp,
                entry.previous_state.value,
                entry.current_state.value,
                entry.trigger_event,
            ])


def write_commands_log(output_dir: str, state: SystemState) -> None:
    """Write *commands_log.csv*."""
    path = os.path.join(output_dir, "commands_log.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "actuator_id", "values"])
        for entry in state.commands_log:
            writer.writerow([
                entry.timestamp,
                entry.actuator_id.value,
                entry.values,
            ])


def write_feature_decisions(output_dir: str, state: SystemState) -> None:
    """Write *feature_decision.csv*."""
    path = os.path.join(output_dir, "feature_decision.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "feature", "decision"])
        for entry in state.feature_decision_log:
            writer.writerow([
                entry.timestamp,
                entry.feature.value,
                entry.decision.value,
            ])


def write_all(output_dir: str, state: SystemState) -> None:
    """Write all three output CSV files to *output_dir*."""
    os.makedirs(output_dir, exist_ok=True)
    write_state_log(output_dir, state)
    write_commands_log(output_dir, state)
    write_feature_decisions(output_dir, state)
