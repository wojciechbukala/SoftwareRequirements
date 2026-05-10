"""
Perception layer – reads raw CSV input files and converts them into
typed event objects for the decision engine.
"""

import csv
import os
from typing import List, Tuple, Union

from .models import (
    DriverEvent,
    DriverEventType,
    SensorEvent,
    SensorType,
)


def _parse_int(value: str, field_name: str, row_num: int) -> int:
    try:
        return int(value)
    except ValueError:
        raise ValueError(
            f"sensor_log.csv row {row_num}: expected integer for '{field_name}', got '{value}'"
        )


def _parse_float(value: str, field_name: str, row_num: int) -> float:
    try:
        return float(value)
    except ValueError:
        raise ValueError(
            f"Row {row_num}: expected numeric value for '{field_name}', got '{value}'"
        )


def load_sensor_events(path: str) -> List[SensorEvent]:
    """
    Parse *sensor_log.csv* into a list of :class:`SensorEvent` objects.

    Expected columns: timestamp, sensor_id, sensor_type, data_value, unit
    """
    events: List[SensorEvent] = []

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row_num, row in enumerate(reader, start=2):  # row 1 is the header
            ts = _parse_int(row["timestamp"].strip(), "timestamp", row_num)
            sensor_id = row["sensor_id"].strip()
            sensor_type_raw = row["sensor_type"].strip()
            data_value = _parse_float(row["data_value"].strip(), "data_value", row_num)
            unit = row["unit"].strip()

            try:
                sensor_type = SensorType(sensor_type_raw)
            except ValueError:
                raise ValueError(
                    f"sensor_log.csv row {row_num}: unknown sensor_type '{sensor_type_raw}'"
                )

            events.append(SensorEvent(
                timestamp=ts,
                sensor_id=sensor_id,
                sensor_type=sensor_type,
                data_value=data_value,
                unit=unit,
            ))

    return events


def load_driver_events(path: str) -> List[DriverEvent]:
    """
    Parse *driver_events.csv* into a list of :class:`DriverEvent` objects.

    Expected columns: timestamp, event_type, value
    Allowed event_type values: ENGAGE, DISENGAGE, STEERING_FORCE
    """
    events: List[DriverEvent] = []

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row_num, row in enumerate(reader, start=2):
            ts = _parse_int(row["timestamp"].strip(), "timestamp", row_num)
            event_type_raw = row["event_type"].strip()
            value_raw = row["value"].strip()

            try:
                event_type = DriverEventType(event_type_raw)
            except ValueError:
                raise ValueError(
                    f"driver_events.csv row {row_num}: unknown event_type '{event_type_raw}'"
                )

            value: float | None = None
            if event_type == DriverEventType.STEERING_FORCE:
                if not value_raw:
                    raise ValueError(
                        f"driver_events.csv row {row_num}: STEERING_FORCE requires a numeric value"
                    )
                value = _parse_float(value_raw, "value", row_num)
            # ENGAGE and DISENGAGE carry no numeric value; ignore whatever is in the column

            events.append(DriverEvent(
                timestamp=ts,
                event_type=event_type,
                value=value,
            ))

    return events


def load_all_events(
    input_dir: str,
) -> List[Union[SensorEvent, DriverEvent]]:
    """
    Load, merge, and sort all input events from *input_dir*.

    Returns events sorted by ascending timestamp (ties cannot occur per DA-04).
    """
    sensor_path = os.path.join(input_dir, "sensor_log.csv")
    driver_path = os.path.join(input_dir, "driver_events.csv")

    sensor_events: List[SensorEvent] = []
    driver_events: List[DriverEvent] = []

    if os.path.exists(sensor_path):
        sensor_events = load_sensor_events(sensor_path)

    if os.path.exists(driver_path):
        driver_events = load_driver_events(driver_path)

    all_events: List[Union[SensorEvent, DriverEvent]] = sensor_events + driver_events
    all_events.sort(key=lambda e: e.timestamp)

    return all_events
