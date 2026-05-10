"""Output layer: writes processed results to CSV output files."""

import csv
import os
from typing import List

from .models import StateTransition, ActuatorCommand, FeatureDecision


def _write_csv(filepath: str, fieldnames: List[str], rows: list) -> None:
    """Write a list of dataclass-like objects to a CSV file with a header row."""
    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({f: getattr(row, f) for f in fieldnames})


def write_state_log(output_dir: str, transitions: List[StateTransition]) -> None:
    """Write state_log.csv to the output directory."""
    _write_csv(
        os.path.join(output_dir, "state_log.csv"),
        ["timestamp", "previous_state", "current_state", "trigger_event"],
        transitions,
    )


def write_commands_log(output_dir: str, commands: List[ActuatorCommand]) -> None:
    """Write commands_log.csv to the output directory."""
    _write_csv(
        os.path.join(output_dir, "commands_log.csv"),
        ["timestamp", "actuator_id", "values"],
        commands,
    )


def write_feature_decisions(output_dir: str, decisions: List[FeatureDecision]) -> None:
    """Write feature_decision.csv to the output directory."""
    _write_csv(
        os.path.join(output_dir, "feature_decision.csv"),
        ["timestamp", "feature", "decision"],
        decisions,
    )


def flush_outputs(output_dir: str, ctx) -> None:
    """Flush all accumulated output records to the output directory."""
    os.makedirs(output_dir, exist_ok=True)
    write_state_log(output_dir, ctx.state_transitions)
    write_commands_log(output_dir, ctx.actuator_commands)
    write_feature_decisions(output_dir, ctx.feature_decisions)
