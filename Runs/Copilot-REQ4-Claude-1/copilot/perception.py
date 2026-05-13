"""Perception layer: parse raw sensor CSV rows into typed SensorEvent objects."""

import csv
from pathlib import Path
from typing import List

from .models import SensorEvent, SensorType


# Map CSV sensor_type strings to enum values (case-insensitive)
_SENSOR_TYPE_MAP = {s.value.lower(): s for s in SensorType}


def load_sensor_events(sensor_log_path: Path) -> List[SensorEvent]:
    """Read *sensor_log.csv* and return a list of :class:`SensorEvent` objects.

    Expected CSV columns: timestamp, sensor_id, sensor_type, data_value, unit.
    """
    events: List[SensorEvent] = []
    with sensor_log_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            raw_type = row["sensor_type"].strip().lower()
            sensor_type = _SENSOR_TYPE_MAP.get(raw_type)
            if sensor_type is None:
                # Unknown sensor type – skip row; real system would log a warning
                continue
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
