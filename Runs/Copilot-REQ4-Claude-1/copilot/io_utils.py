"""CSV I/O utilities for reading inputs and writing outputs."""

import csv
from pathlib import Path
from typing import List

from .models import (
    CommandEntry,
    DriverEvent,
    DriverEventType,
    FeatureDecisionEntry,
    StateLogEntry,
)


# ── Input readers ─────────────────────────────────────────────────────────────

def load_driver_events(driver_events_path: Path) -> List[DriverEvent]:
    """Read *driver_events.csv* and return typed :class:`DriverEvent` objects.

    Expected columns: timestamp, event_type, value.
    The *value* column is optional for ENGAGE / DISENGAGE rows.
    """
    events: List[DriverEvent] = []
    with driver_events_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            raw_type = row["event_type"].strip().upper()
            try:
                event_type = DriverEventType(raw_type)
            except ValueError:
                continue  # Unknown event type – skip

            raw_value = row.get("value", "").strip()
            value: float | None = float(raw_value) if raw_value else None

            events.append(
                DriverEvent(
                    timestamp=float(row["timestamp"]),
                    event_type=event_type,
                    value=value,
                )
            )
    return events


# ── Output writers ────────────────────────────────────────────────────────────

def write_state_log(entries: List[StateLogEntry], output_path: Path) -> None:
    """Write state transition records to *state_log.csv*."""
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
        for e in entries:
            writer.writerow([e.timestamp, e.previous_state, e.current_state, e.trigger_event])


def write_commands_log(entries: List[CommandEntry], output_path: Path) -> None:
    """Write actuator command records to *commands_log.csv*."""
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "actuator_id", "values"])
        for e in entries:
            writer.writerow([e.timestamp, e.actuator_id, e.values])


def write_feature_decisions(entries: List[FeatureDecisionEntry], output_path: Path) -> None:
    """Write ADAS feature decision records to *feature_decision.csv*."""
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "feature", "decision"])
        for e in entries:
            writer.writerow([e.timestamp, e.feature, e.decision])
