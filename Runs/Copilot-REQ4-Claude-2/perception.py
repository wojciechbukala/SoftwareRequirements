"""
Perception layer — reads sensor and driver event CSV files.

Responsible for parsing raw input data into typed event objects
that the decision engine can process.
"""

import csv
from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass
class SensorEvent:
    """A single sensor reading (Lidar or Camera)."""
    timestamp: float
    sensor_id: str
    sensor_type: str   # 'Lidar' or 'Camera'
    data_value: float
    unit: str


@dataclass
class DriverEvent:
    """A single driver input (ENGAGE, DISENGAGE, or STEERING_FORCE)."""
    timestamp: float
    event_type: str       # 'ENGAGE', 'DISENGAGE', or 'STEERING_FORCE'
    value: Optional[float]  # force magnitude; None for ENGAGE / DISENGAGE


Event = Union[SensorEvent, DriverEvent]


def read_sensor_log(filepath: str) -> List[SensorEvent]:
    """Parse sensor_log.csv and return a list of SensorEvent objects."""
    events: List[SensorEvent] = []
    with open(filepath, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            events.append(SensorEvent(
                timestamp=float(row['timestamp']),
                sensor_id=row['sensor_id'].strip(),
                sensor_type=row['sensor_type'].strip(),
                data_value=float(row['data_value']),
                unit=row['unit'].strip(),
            ))
    return events


def read_driver_events(filepath: str) -> List[DriverEvent]:
    """Parse driver_events.csv and return a list of DriverEvent objects."""
    events: List[DriverEvent] = []
    with open(filepath, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            raw_value = row.get('value', '').strip()
            value = float(raw_value) if raw_value else None
            events.append(DriverEvent(
                timestamp=float(row['timestamp']),
                event_type=row['event_type'].strip(),
                value=value,
            ))
    return events
