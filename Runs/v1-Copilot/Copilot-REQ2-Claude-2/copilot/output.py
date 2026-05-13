"""
Output layer: collects and writes Copilot records to the three CSV output files (SP4).

Output files:
  state_log.csv        – state transition records (FR-01, FR-03).
  commands_log.csv     – actuator commands issued (FR-02, FR-03).
  feature_decision.csv – autonomous feature decisions (FR-02).
"""

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .actuator import ActuatorCommand
from .features import FeatureDecision
from .state_machine import State


def _fmt_timestamp(ts: float) -> str:
    """Format a Unix timestamp as a UTC ISO-8601 string for CSV output."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")


@dataclass
class _StateRecord:
    timestamp: float
    previous_state: State
    current_state: State
    trigger_event: str


class OutputWriter:
    """Accumulates output records in memory and flushes them to CSV files on demand."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        self._state_records: List[_StateRecord] = []
        self._command_records: List[ActuatorCommand] = []
        self._decision_records: List[FeatureDecision] = []

    # ------------------------------------------------------------------
    # Record collection API
    # ------------------------------------------------------------------

    def record_state_transition(
        self,
        timestamp: float,
        previous_state: State,
        current_state: State,
        trigger_event: str,
    ) -> None:
        """Append a state-transition record.  Only actual state changes should be passed."""
        self._state_records.append(
            _StateRecord(timestamp, previous_state, current_state, trigger_event)
        )

    def record_command(self, command: ActuatorCommand) -> None:
        """Append an actuator command record."""
        self._command_records.append(command)

    def record_decision(self, decision: FeatureDecision) -> None:
        """Append a feature decision record."""
        self._decision_records.append(decision)

    # ------------------------------------------------------------------
    # Flush to disk
    # ------------------------------------------------------------------

    def flush(self) -> None:
        """Write all collected records to their respective CSV files."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._write_state_log()
        self._write_commands_log()
        self._write_feature_decisions()

    def _write_state_log(self) -> None:
        path = self._output_dir / "state_log.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
            for rec in self._state_records:
                writer.writerow(
                    [
                        _fmt_timestamp(rec.timestamp),
                        rec.previous_state.value,
                        rec.current_state.value,
                        rec.trigger_event,
                    ]
                )

    def _write_commands_log(self) -> None:
        path = self._output_dir / "commands_log.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["timestamp", "actuator_id", "values"])
            for cmd in self._command_records:
                writer.writerow([_fmt_timestamp(cmd.timestamp), cmd.actuator_id, cmd.values])

    def _write_feature_decisions(self) -> None:
        path = self._output_dir / "feature_decision.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["timestamp", "feature", "decision"])
            for dec in self._decision_records:
                writer.writerow([_fmt_timestamp(dec.timestamp), dec.feature, dec.decision])
