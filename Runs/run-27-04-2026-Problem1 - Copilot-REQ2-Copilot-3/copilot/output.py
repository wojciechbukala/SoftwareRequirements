"""Output layer: buffers and writes the three output CSV files (FR-02, FR-05)."""

import csv
import os
from typing import List


class OutputWriter:
    """Collects state transitions, actuator commands, and feature decisions in
    memory and flushes them to CSV files at the end of the simulation run."""

    # CSV header definitions per the design constraints in section 3.5.
    _STATE_LOG_HEADERS = ["timestamp", "previous_state", "current_state", "trigger_event"]
    _COMMANDS_LOG_HEADERS = ["timestamp", "actuator_id", "values"]
    _FEATURE_DECISION_HEADERS = ["timestamp", "feature", "decision"]

    def __init__(self, output_dir: str) -> None:
        self._output_dir = output_dir
        self._state_log: List[dict] = []
        self._commands_log: List[dict] = []
        self._feature_decisions: List[dict] = []

    # ------------------------------------------------------------------
    # Recording methods (called by the state machine)
    # ------------------------------------------------------------------

    def record_state_transition(
        self, timestamp: float, previous: str, current: str, trigger: str
    ) -> None:
        """Buffer one row for state_log.csv (SP4)."""
        self._state_log.append(
            {
                "timestamp": timestamp,
                "previous_state": previous,
                "current_state": current,
                "trigger_event": trigger,
            }
        )

    def record_command(self, timestamp: float, actuator_id: str, values: str) -> None:
        """Buffer one row for commands_log.csv (SP5)."""
        self._commands_log.append(
            {
                "timestamp": timestamp,
                "actuator_id": actuator_id,
                "values": values,
            }
        )

    def record_feature_decision(self, timestamp: float, feature: str, decision: str) -> None:
        """Buffer one row for feature_decision.csv (SP4)."""
        self._feature_decisions.append(
            {
                "timestamp": timestamp,
                "feature": feature,
                "decision": decision,
            }
        )

    # ------------------------------------------------------------------
    # Flush to disk
    # ------------------------------------------------------------------

    def flush(self) -> None:
        """Write all buffered records to their respective CSV files (FR-05, PF-02)."""
        os.makedirs(self._output_dir, exist_ok=True)
        self._write_csv("state_log.csv", self._STATE_LOG_HEADERS, self._state_log)
        self._write_csv("commands_log.csv", self._COMMANDS_LOG_HEADERS, self._commands_log)
        self._write_csv("feature_decision.csv", self._FEATURE_DECISION_HEADERS, self._feature_decisions)

    def _write_csv(self, filename: str, headers: List[str], rows: List[dict]) -> None:
        path = os.path.join(self._output_dir, filename)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
