"""Perception layer: parse raw CSV inputs into typed event objects."""

import csv
from pathlib import Path
from typing import List

from .models import DriverEvent, DriverEventType, SensorEvent, SensorType


def parse_sensor_log(path: Path) -> List[SensorEvent]:
    """
    Read *sensor_log.csv* and return a list of :class:`SensorEvent` objects.

    Expected columns: timestamp, sensor_id, sensor_type, data_value, unit.
    """
    events: List[SensorEvent] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            events.append(
                SensorEvent(
                    timestamp=int(row["timestamp"]),
                    sensor_id=row["sensor_id"].strip(),
                    sensor_type=SensorType(row["sensor_type"].strip()),
                    data_value=float(row["data_value"]),
                    unit=row["unit"].strip(),
                )
            )
    return events


def parse_driver_events(path: Path) -> List[DriverEvent]:
    """
    Read *driver_events.csv* and return a list of :class:`DriverEvent` objects.

    Expected columns: timestamp, event_type, value.
    The *value* column is required only for STEERING_FORCE events; it is
    ignored (treated as *None*) for ENGAGE and DISENGAGE.
    """
    events: List[DriverEvent] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            event_type = DriverEventType(row["event_type"].strip())
            raw_value = row.get("value", "").strip()
            value = float(raw_value) if raw_value else None
            events.append(
                DriverEvent(
                    timestamp=int(row["timestamp"]),
                    event_type=event_type,
                    value=value,
                )
            )
    return events
