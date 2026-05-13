"""Perception layer: reads sensor and driver event CSV files."""
import csv
from pathlib import Path
from typing import List, Union

from models import DriverEvent, DriverEventType, SensorEvent, SensorType


def load_sensor_events(input_dir: Path) -> List[SensorEvent]:
    """Parse sensor_log.csv into SensorEvent objects."""
    path = input_dir / "sensor_log.csv"
    events: List[SensorEvent] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            raw_type = row["sensor_type"].strip().upper()
            sensor_type = SensorType.LIDAR if raw_type == "LIDAR" else SensorType.CAMERA
            events.append(SensorEvent(
                timestamp=int(row["timestamp"]),
                sensor_id=row["sensor_id"].strip(),
                sensor_type=sensor_type,
                data_value=float(row["data_value"]),
                unit=row["unit"].strip(),
            ))
    return events


def load_driver_events(input_dir: Path) -> List[DriverEvent]:
    """Parse driver_events.csv into DriverEvent objects."""
    path = input_dir / "driver_events.csv"
    events: List[DriverEvent] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            event_type = DriverEventType[row["event_type"].strip().upper()]
            raw_value = row["value"].strip()
            value = float(raw_value) if raw_value else None
            events.append(DriverEvent(
                timestamp=int(row["timestamp"]),
                event_type=event_type,
                value=value,
            ))
    return events


def load_all_events(input_dir: Path) -> List[Union[SensorEvent, DriverEvent]]:
    """Load, merge and sort all input events by timestamp."""
    all_events: List[Union[SensorEvent, DriverEvent]] = []
    all_events.extend(load_sensor_events(input_dir))
    all_events.extend(load_driver_events(input_dir))
    all_events.sort(key=lambda e: e.timestamp)
    return all_events
