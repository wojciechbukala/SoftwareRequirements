"""Perception layer: reads and merges input CSV event streams."""

import csv
import os
from typing import List, Union

from .models import SensorEvent, DriverEvent


def read_sensor_events(filepath: str) -> List[SensorEvent]:
    """Read all sensor events from sensor_log.csv in ascending timestamp order."""
    events: List[SensorEvent] = []
    with open(filepath, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            events.append(SensorEvent(
                timestamp=float(row["timestamp"]),
                sensor_id=row["sensor_id"],
                sensor_type=row["sensor_type"],
                data_value=float(row["data_value"]),
                unit=row["unit"],
            ))
    return events


def read_driver_events(filepath: str) -> List[DriverEvent]:
    """Read all driver events from driver_events.csv in ascending timestamp order."""
    events: List[DriverEvent] = []
    with open(filepath, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            events.append(DriverEvent(
                timestamp=float(row["timestamp"]),
                event_type=row["event_type"],
                value=float(row["value"]),
            ))
    return events


def merge_events(
    sensor_events: List[SensorEvent],
    driver_events: List[DriverEvent],
) -> List[Union[SensorEvent, DriverEvent]]:
    """Merge two event streams into a single stream sorted by ascending timestamp.

    When timestamps are equal the original relative order within each source list
    is preserved via Python's stable sort.
    """
    tagged = (
        [(e.timestamp, 0, e) for e in sensor_events]
        + [(e.timestamp, 1, e) for e in driver_events]
    )
    tagged.sort(key=lambda x: (x[0], x[1]))
    return [item[2] for item in tagged]


def load_events(input_dir: str):
    """Load and merge all events from the input directory."""
    sensor_path = os.path.join(input_dir, "sensor_log.csv")
    driver_path = os.path.join(input_dir, "driver_events.csv")
    sensor_events = read_sensor_events(sensor_path)
    driver_events = read_driver_events(driver_path)
    return merge_events(sensor_events, driver_events)
