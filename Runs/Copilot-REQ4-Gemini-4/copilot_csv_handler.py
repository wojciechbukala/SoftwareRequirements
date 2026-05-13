import csv
import os
from collections import namedtuple
from typing import List, Dict, Union

from copilot_constants import SensorType, DriverEventType, State, Actuator, FeatureDecisionKind, DecisionValue

# Define named tuples for clarity and consistency
SensorEventData = namedtuple('SensorEventData', ['timestamp', 'sensor_id', 'sensor_type', 'data_value', 'unit'])
DriverEventData = namedtuple('DriverEventData', ['timestamp', 'event_type', 'value'])
StateLogEntry = namedtuple('StateLogEntry', ['timestamp', 'previous_state', 'current_state', 'trigger_event'])
CommandLogEntry = namedtuple('CommandLogEntry', ['timestamp', 'actuator_id', 'values'])
FeatureDecisionLogEntry = namedtuple('FeatureDecisionLogEntry', ['timestamp', 'feature', 'decision'])

def read_sensor_log(file_path: str) -> List[SensorEventData]:
    """Reads sensor log data from a CSV file."""
    events = []
    if not os.path.exists(file_path):
        print(f"Error: Sensor log file not found at {file_path}")
        return events
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    timestamp = float(row['timestamp'])
                    sensor_id = row['sensor_id']
                    sensor_type_str = row['sensor_type']
                    data_value = float(row['data_value'])
                    unit = row['unit']

                    if sensor_type_str not in [st.value for st in SensorType]:
                        print(f"Warning: Unknown sensor type '{sensor_type_str}' at timestamp {timestamp}. Skipping event.")
                        continue
                    sensor_type = SensorType(sensor_type_str)

                    events.append(SensorEventData(timestamp, sensor_id, sensor_type, data_value, unit))
                except (ValueError, KeyError) as e:
                    print(f"Error parsing sensor log row: {row}. Details: {e}. Skipping row.")
    except Exception as e:
        print(f"Error reading sensor log file {file_path}: {e}")
    return events

def read_driver_events(file_path: str) -> List[DriverEventData]:
    """Reads driver event data from a CSV file."""
    events = []
    if not os.path.exists(file_path):
        print(f"Error: Driver events file not found at {file_path}")
        return events
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    timestamp = float(row['timestamp'])
                    event_type_str = row['event_type']
                    value = float(row['value']) if row['value'] else None

                    if event_type_str not in [det.value for det in DriverEventType]:
                        print(f"Warning: Unknown driver event type '{event_type_str}' at timestamp {timestamp}. Skipping event.")
                        continue
                    event_type = DriverEventType(event_type_str)

                    events.append(DriverEventData(timestamp, event_type, value))
                except (ValueError, KeyError) as e:
                    print(f"Error parsing driver event row: {row}. Details: {e}. Skipping row.")
    except Exception as e:
        print(f"Error reading driver events file {file_path}: {e}")
    return events

def write_state_log(file_path: str, log_entries: List[StateLogEntry]):
    """Writes state log entries to a CSV file."""
    headers = ['timestamp', 'previous_state', 'current_state', 'trigger_event']
    try:
        with open(file_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for entry in log_entries:
                writer.writerow([entry.timestamp, entry.previous_state.value, entry.current_state.value, entry.trigger_event])
    except Exception as e:
        print(f"Error writing state log to {file_path}: {e}")

def write_commands_log(file_path: str, log_entries: List[CommandLogEntry]):
    """Writes command log entries to a CSV file."""
    headers = ['timestamp', 'actuator_id', 'values']
    try:
        with open(file_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for entry in log_entries:
                # 'values' field can be string or float, ensure it's written correctly
                val_to_write = entry.values.value if isinstance(entry.values, Enum) else entry.values
                writer.writerow([entry.timestamp, entry.actuator_id.value, val_to_write])
    except Exception as e:
        print(f"Error writing command log to {file_path}: {e}")

def write_feature_decision_log(file_path: str, log_entries: List[FeatureDecisionLogEntry]):
    """Writes feature decision log entries to a CSV file."""
    headers = ['timestamp', 'feature', 'decision']
    try:
        with open(file_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for entry in log_entries:
                # 'decision' field can be string or float, ensure it's written correctly
                dec_to_write = entry.decision.value if isinstance(entry.decision, Enum) else entry.decision
                writer.writerow([entry.timestamp, entry.feature.value, dec_to_write])
    except Exception as e:
        print(f"Error writing feature decision log to {file_path}: {e}")
