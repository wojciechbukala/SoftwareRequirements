"""
Output layer — CSV serialisation of simulation results.

All files are written as UTF-8 comma-separated values with a header row.

Output files produced
---------------------
* ``state_log.csv``       — every state *change* with its triggering event.
* ``commands_log.csv``    — every actuator command that was dispatched.
* ``feature_decision.csv``— every feature evaluation result.
"""

from __future__ import annotations

import csv
from pathlib import Path

from copilot.actuator import ActuatorCommand
from copilot.decision import FeatureDecision
from copilot.state_machine import StateTransition


# ---------------------------------------------------------------------------
# Writer helpers
# ---------------------------------------------------------------------------

def write_state_log(
    path: Path,
    transitions: list[StateTransition],
) -> None:
    """
    Write all recorded state transitions to *state_log.csv*.

    Only actual state changes are included (same-state records are never
    created by :class:`~copilot.state_machine.StateMachine`).

    CSV columns: ``timestamp, previous_state, current_state, trigger_event``

    Args:
        path:        Directory in which to create ``state_log.csv``.
        transitions: Ordered list of :class:`~copilot.state_machine.StateTransition`
                     objects collected during the simulation run.
    """
    output_file = path / "state_log.csv"
    with output_file.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
        for t in transitions:
            writer.writerow([t.timestamp, t.previous_state, t.current_state, t.trigger_event])


def write_commands_log(
    path: Path,
    commands: list[ActuatorCommand],
) -> None:
    """
    Write all dispatched actuator commands to *commands_log.csv*.

    CSV columns: ``timestamp, actuator_id, values``

    Args:
        path:     Directory in which to create ``commands_log.csv``.
        commands: Ordered list of :class:`~copilot.actuator.ActuatorCommand`
                  objects collected during the simulation run.
    """
    output_file = path / "commands_log.csv"
    with output_file.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "actuator_id", "values"])
        for cmd in commands:
            writer.writerow([cmd.timestamp, cmd.actuator_id, cmd.values])


def write_feature_decisions(
    path: Path,
    decisions: list[FeatureDecision],
) -> None:
    """
    Write all feature evaluation results to *feature_decision.csv*.

    CSV columns: ``timestamp, feature, decision``

    Args:
        path:      Directory in which to create ``feature_decision.csv``.
        decisions: Ordered list of :class:`~copilot.decision.FeatureDecision`
                   objects collected during the simulation run.
    """
    output_file = path / "feature_decision.csv"
    with output_file.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "feature", "decision"])
        for d in decisions:
            writer.writerow([d.timestamp, d.feature, d.decision])
