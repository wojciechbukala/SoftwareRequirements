"""
Perception layer: parses input CSV files into typed event objects.

Responsible for reading sensor_log.csv and driver_events.csv and exposing
a unified, timestamp-sorted event stream to the decision layer.
"""

import csv
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Union


class SensorType(Enum):
    """Identifies the physical sensor that produced a reading."""

    LIDAR = "Lidar"
    CAMERA = "Camera"


class DriverEventType(Enum):
    """Classifies driver-initiated control events."""

    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"


@dataclass
class SensorEvent:
    """A single sensor reading delivered to the Copilot system."""

    timestamp: float       # seconds since epoch / simulation start
    sensor_id: str         # physical sensor identifier
    sensor_type: SensorType
    data_value: float      # raw measurement (distance in m for Lidar, lane offset for Camera)
    unit: str              # measurement unit string


@dataclass
class DriverEvent:
    """A single driver-initiated event (button press or steering input)."""

    timestamp: float
    event_type: DriverEventType
    value: Optional[float]  # Force in Newtons — only present for STEERING_FORCE


# Convenience union type used throughout the system
AnyEvent = Union[SensorEvent, DriverEvent]


def load_sensor_events(path: str) -> List[SensorEvent]:
    """
    Read *sensor_log.csv* and return a list of SensorEvent objects.

    Expected columns: timestamp, sensor_id, sensor_type, data_value, unit
    """
    events: List[SensorEvent] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            raw_type = row["sensor_type"].strip()
            try:
                sensor_type = SensorType(raw_type)
            except ValueError as exc:
                raise ValueError(f"Unrecognised sensor_type {raw_type!r} in {path}") from exc
            events.append(
                SensorEvent(
                    timestamp=float(row["timestamp"]),
                    sensor_id=row["sensor_id"].strip(),
                    sensor_type=sensor_type,
                    data_value=float(row["data_value"]),
                    unit=row["unit"].strip(),
                )
            )
    return events


def load_driver_events(path: str) -> List[DriverEvent]:
    """
    Read *driver_events.csv* and return a list of DriverEvent objects.

    Expected columns: timestamp, event_type, value
    The *value* field is required only for STEERING_FORCE events.
    """
    events: List[DriverEvent] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            raw_type = row["event_type"].strip()
            try:
                event_type = DriverEventType(raw_type)
            except ValueError as exc:
                raise ValueError(f"Unrecognised event_type {raw_type!r} in {path}") from exc
            raw_value = row.get("value", "").strip()
            value = float(raw_value) if raw_value else None
            events.append(
                DriverEvent(
                    timestamp=float(row["timestamp"]),
                    event_type=event_type,
                    value=value,
                )
            )
    return events


def merge_and_sort_events(
    sensor_events: List[SensorEvent],
    driver_events: List[DriverEvent],
) -> List[AnyEvent]:
    """
    Combine sensor and driver event lists into a single stream sorted by
    timestamp.  DA-04 guarantees unique timestamps, so ordering is stable.
    """
    combined: List[AnyEvent] = list(sensor_events) + list(driver_events)
    combined.sort(key=lambda e: e.timestamp)
    return combined
