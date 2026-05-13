"""
Actuator control layer — writes simulation results to CSV output files.

Translates the decision engine's output records into the three required
output files: state_log.csv, commands_log.csv, and feature_decision.csv.
"""

import csv
from typing import List

from decision import StateLogEntry, CommandEntry, FeatureDecisionEntry


def write_state_log(filepath: str, entries: List[StateLogEntry]) -> None:
    """Write state transition log to state_log.csv."""
    with open(filepath, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh)
        writer.writerow(['timestamp', 'previous_state', 'current_state', 'trigger_event'])
        for e in entries:
            writer.writerow([e.timestamp, e.previous_state, e.current_state, e.trigger_event])


def write_commands_log(filepath: str, entries: List[CommandEntry]) -> None:
    """Write actuator command log to commands_log.csv."""
    with open(filepath, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh)
        writer.writerow(['timestamp', 'actuator_id', 'values'])
        for e in entries:
            writer.writerow([e.timestamp, e.actuator_id, e.values])


def write_feature_decisions(filepath: str, entries: List[FeatureDecisionEntry]) -> None:
    """Write feature decision log to feature_decision.csv."""
    with open(filepath, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh)
        writer.writerow(['timestamp', 'feature', 'decision'])
        for e in entries:
            writer.writerow([e.timestamp, e.feature, e.decision])
