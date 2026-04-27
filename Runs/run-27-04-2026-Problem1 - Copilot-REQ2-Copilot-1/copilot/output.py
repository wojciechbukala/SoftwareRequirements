"""Output layer: writes state transitions, actuator commands, and feature decisions to CSV files."""

import csv
from pathlib import Path

from copilot.actuator import ActuatorCommand
from copilot.decision import FeatureDecision


class OutputWriter:
    """Opens and manages all three output CSV files for the duration of a run."""

    def __init__(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)

        self._state_fh = open(output_dir / "state_log.csv", "w", newline="", encoding="utf-8")
        self._commands_fh = open(output_dir / "commands_log.csv", "w", newline="", encoding="utf-8")
        self._decisions_fh = open(output_dir / "feature_decision.csv", "w", newline="", encoding="utf-8")

        self._state_writer = csv.writer(self._state_fh)
        self._commands_writer = csv.writer(self._commands_fh)
        self._decisions_writer = csv.writer(self._decisions_fh)

        # Write headers (FR-05 / section 3.5)
        self._state_writer.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
        self._commands_writer.writerow(["timestamp", "actuator_id", "values"])
        self._decisions_writer.writerow(["timestamp", "feature", "decision"])

    def write_state_transition(
        self,
        timestamp_raw: str,
        previous_state: str,
        current_state: str,
        trigger_event: str,
    ) -> None:
        """Append one row to state_log.csv."""
        self._state_writer.writerow([timestamp_raw, previous_state, current_state, trigger_event])

    def write_command(self, command: ActuatorCommand) -> None:
        """Append one row to commands_log.csv."""
        self._commands_writer.writerow([command.timestamp_raw, command.actuator_id, command.values])

    def write_decision(self, decision: FeatureDecision) -> None:
        """Append one row to feature_decision.csv."""
        self._decisions_writer.writerow([decision.timestamp_raw, decision.feature, decision.decision])

    def flush(self) -> None:
        """Flush and close all output files."""
        for fh in (self._state_fh, self._commands_fh, self._decisions_fh):
            fh.flush()
            fh.close()
