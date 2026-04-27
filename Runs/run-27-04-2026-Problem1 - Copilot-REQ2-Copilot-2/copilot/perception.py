"""
Perception layer: reads and parses sensor events and driver events from CSV input files.

This module is responsible solely for ingesting raw CSV data and converting it into
typed, in-memory event objects consumed by the rest of the system.
"""

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
)


def parse_timestamp(ts_str: str) -> float:
    """Convert a timestamp string to a float representing seconds since the Unix epoch.

    Accepts both plain numeric strings (already seconds since epoch) and
    ISO-8601 / common datetime strings (interpreted as UTC).
    """
    try:
        return float(ts_str)
    except ValueError:
        pass

    for fmt in _DATETIME_FORMATS:
        try:
            dt = datetime.strptime(ts_str.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue

    raise ValueError(f"Unrecognised timestamp format: {ts_str!r}")


# ---------------------------------------------------------------------------
# Event data classes  (SP1 / SP2 shared phenomena)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SensorEvent:
    """A single periodic reading produced by one of the on-board sensors (SP1)."""

    timestamp: float     # seconds since Unix epoch
    sensor_id: str
    sensor_type: str     # normalised to lowercase, e.g. 'lidar' or 'camera'
    data_value: float
    unit: str


@dataclass(frozen=True)
class DriverEvent:
    """A single interaction originating from the driver (SP2 / SP3)."""

    timestamp: float     # seconds since Unix epoch
    event_type: str      # 'ENGAGE', 'DISENGAGE', or 'STEERING_FORCE'
    value: float         # Newtons for STEERING_FORCE; 0.0 otherwise


# ---------------------------------------------------------------------------
# CSV readers
# ---------------------------------------------------------------------------

def load_sensor_events(path: Path) -> List[SensorEvent]:
    """Read *sensor_log.csv* and return the contained events as SensorEvent objects."""
    events: List[SensorEvent] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            events.append(
                SensorEvent(
                    timestamp=parse_timestamp(row["timestamp"]),
                    sensor_id=row["sensor_id"].strip(),
                    sensor_type=row["sensor_type"].strip().lower(),
                    data_value=float(row["data_value"]),
                    unit=row["unit"].strip(),
                )
            )
    return events


def load_driver_events(path: Path) -> List[DriverEvent]:
    """Read *driver_events.csv* and return the contained events as DriverEvent objects."""
    events: List[DriverEvent] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            raw_value = row.get("value", "").strip()
            events.append(
                DriverEvent(
                    timestamp=parse_timestamp(row["timestamp"]),
                    event_type=row["event_type"].strip().upper(),
                    value=float(raw_value) if raw_value else 0.0,
                )
            )
    return events
