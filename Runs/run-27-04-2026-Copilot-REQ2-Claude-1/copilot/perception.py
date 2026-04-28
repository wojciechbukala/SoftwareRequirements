"""Perception layer: reads and parses input CSV files into event objects."""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Union


@dataclass
class SensorEvent:
    """A single reading from an on-board sensor."""
    timestamp: float        # parsed numeric seconds for comparisons
    timestamp_raw: str      # original string preserved for output
    sensor_id: str
    sensor_type: str        # 'lidar' or 'camera' (lower-cased)
    data_value: float
    unit: str


@dataclass
class DriverEvent:
    """A single interaction originating from the driver."""
    timestamp: float
    timestamp_raw: str
    event_type: str         # ENGAGE | DISENGAGE | STEERING_FORCE
    value: str


# Union type for a merged event entry
Event = Union[SensorEvent, DriverEvent]
EventStream = List[Tuple[str, Event]]  # ('sensor'|'driver', event)


def _parse_timestamp(ts_str: str) -> float:
    """Parse a timestamp string into a float.

    Accepts plain numeric strings (e.g. '0', '120.5') and ISO-8601 datetime
    strings (e.g. '2024-01-01T00:02:00').  Returns seconds as a float.
    """
    try:
        return float(ts_str.strip())
    except ValueError:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(ts_str.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()


def load_sensor_events(input_dir: Path) -> List[SensorEvent]:
    """Read sensor_log.csv and return a list of SensorEvent objects."""
    events: List[SensorEvent] = []
    path = input_dir / "sensor_log.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            events.append(SensorEvent(
                timestamp=_parse_timestamp(row["timestamp"]),
                timestamp_raw=row["timestamp"].strip(),
                sensor_id=row["sensor_id"].strip(),
                sensor_type=row["sensor_type"].strip().lower(),
                data_value=float(row["data_value"]),
                unit=row["unit"].strip(),
            ))
    return events


def load_driver_events(input_dir: Path) -> List[DriverEvent]:
    """Read driver_events.csv and return a list of DriverEvent objects."""
    events: List[DriverEvent] = []
    path = input_dir / "driver_events.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            events.append(DriverEvent(
                timestamp=_parse_timestamp(row["timestamp"]),
                timestamp_raw=row["timestamp"].strip(),
                event_type=row["event_type"].strip().upper(),
                value=row["value"].strip(),
            ))
    return events


def load_events(input_dir: Path) -> EventStream:
    """Load sensor and driver events, merge them in ascending timestamp order.

    When two events share the same timestamp, sensor events are placed before
    driver events so that environmental readings are processed first.
    """
    sensor_events = load_sensor_events(input_dir)
    driver_events = load_driver_events(input_dir)

    combined: List[Tuple[float, int, str, Event]] = []
    for e in sensor_events:
        combined.append((e.timestamp, 0, "sensor", e))
    for e in driver_events:
        combined.append((e.timestamp, 1, "driver", e))

    combined.sort(key=lambda x: (x[0], x[1]))
    return [(kind, event) for _, _, kind, event in combined]
