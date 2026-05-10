"""Perception layer: reads sensor and driver event CSVs into unified event stream."""

import csv
import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SensorEvent:
    """A single reading from an on-board sensor."""
    timestamp: float
    sensor_id: str
    sensor_type: str
    data_value: float
    unit: str


@dataclass
class DriverEvent:
    """A single interaction originating from the driver."""
    timestamp: float
    event_type: str          # ENGAGE | DISENGAGE | STEERING_FORCE
    value: Optional[float]   # Newton value for STEERING_FORCE; None otherwise


def load_sensor_events(input_dir: str) -> List[SensorEvent]:
    """Read all rows from sensor_log.csv and return them as SensorEvent objects."""
    path = os.path.join(input_dir, "sensor_log.csv")
    events: List[SensorEvent] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            events.append(
                SensorEvent(
                    timestamp=float(row["timestamp"]),
                    sensor_id=row["sensor_id"].strip(),
                    sensor_type=row["sensor_type"].strip(),
                    data_value=float(row["data_value"]),
                    unit=row["unit"].strip(),
                )
            )
    return events


def load_driver_events(input_dir: str) -> List[DriverEvent]:
    """Read all rows from driver_events.csv and return them as DriverEvent objects."""
    path = os.path.join(input_dir, "driver_events.csv")
    events: List[DriverEvent] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            raw_value = row["value"].strip()
            value: Optional[float] = float(raw_value) if raw_value else None
            events.append(
                DriverEvent(
                    timestamp=float(row["timestamp"]),
                    event_type=row["event_type"].strip(),
                    value=value,
                )
            )
    return events


def merge_event_stream(
    sensor_events: List[SensorEvent],
    driver_events: List[DriverEvent],
) -> list:
    """Merge sensor and driver events into a single ascending-timestamp stream (PF-02)."""
    combined = []
    for e in sensor_events:
        combined.append(("sensor", e))
    for e in driver_events:
        combined.append(("driver", e))
    combined.sort(key=lambda pair: pair[1].timestamp)
    return combined
