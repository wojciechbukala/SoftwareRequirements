import argparse
import os
import sys
from typing import List, Union

from constants import SENSOR_LOG_HEADERS, DRIVER_EVENTS_HEADERS, SystemState, SensorType, DriverEventType, \
    STATE_LOG_HEADERS, COMMANDS_LOG_HEADERS, FEATURE_DECISION_HEADERS
from csv_utils import read_csv, write_csv
from data_models import SensorEvent, DriverEvent, MergedEvent, StateLogEntry, CommandLogEntry, FeatureDecisionEntry
from copilot_logic import Copilot


def parse_sensor_event(row: dict) -> SensorEvent:
    return SensorEvent(
        timestamp=float(row["timestamp"]),
        sensor_id=row["sensor_id"],
        sensor_type=SensorType(row["sensor_type"]),
        data_value=float(row["data_value"]),
        unit=row["unit"],
    )


def parse_driver_event(row: dict) -> DriverEvent:
    event_type = DriverEventType(row["event_type"])
    value: Union[float, str]
    if event_type == DriverEventType.STEERING_FORCE:
        value = float(row["value"])
    else:
        value = row["value"] # ENGAGE/DISENGAGE might not have a numerical value, or it's a string representation
    return DriverEvent(
        timestamp=float(row["timestamp"]),
        event_type=event_type,
        value=value,
    )


def main():
    parser = argparse.ArgumentParser(description="Copilot driver-assistance system simulation.")
    parser.add_argument("--input", required=True,
                        help="Path to the input directory containing sensor_log.csv and driver_events.csv.")
    parser.add_argument("--output", required=True,
                        help="Path to the output directory for state_log.csv, commands_log.csv, and feature_decision.csv.")

    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    if not os.path.isdir(input_dir):
        print(f"Error: Input directory '{input_dir}' not found.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    print(f"Copilot simulation started with input: {input_dir}, output: {output_dir}")

    # --- Read Input Files ---
    sensor_log_path = os.path.join(input_dir, "sensor_log.csv")
    driver_events_path = os.path.join(input_dir, "driver_events.csv")

    try:
        sensor_data = read_csv(sensor_log_path, SENSOR_LOG_HEADERS)
        driver_data = read_csv(driver_events_path, DRIVER_EVENTS_HEADERS)
    except FileNotFoundError as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error with CSV format: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Parse and Merge Events ---
    all_events: List[MergedEvent] = []

    for row in sensor_data:
        sensor_event = parse_sensor_event(row)
        all_events.append(MergedEvent(timestamp=sensor_event.timestamp, event_type="sensor", data=sensor_event))

    for row in driver_data:
        driver_event = parse_driver_event(row)
        all_events.append(MergedEvent(timestamp=driver_event.timestamp, event_type="driver", data=driver_event))

    # Sort all events by timestamp
    all_events.sort()

    # --- Run Simulation ---
    copilot = Copilot()

    for merged_event in all_events:
        copilot.process_event(merged_event.timestamp, merged_event.data)

    # --- Write Output Files ---
    state_log_output_path = os.path.join(output_dir, "state_log.csv")
    commands_log_output_path = os.path.join(output_dir, "commands_log.csv")
    feature_decision_output_path = os.path.join(output_dir, "feature_decision.csv")

    # Convert dataclass objects to dictionaries for CSV writing
    state_log_dicts = [entry.__dict__ for entry in copilot.state_log]
    commands_log_dicts = [entry.__dict__ for entry in copilot.commands_log]
    feature_decision_log_dicts = [entry.__dict__ for entry in copilot.feature_decision_log]

    # Handle Enum values for writing
    for d in state_log_dicts:
        d["previous_state"] = d["previous_state"].value
        d["current_state"] = d["current_state"].value
    for d in commands_log_dicts:
        d["actuator_id"] = d["actuator_id"].value
    for d in feature_decision_log_dicts:
        d["feature"] = d["feature"].value

    try:
        write_csv(state_log_output_path, STATE_LOG_HEADERS, state_log_dicts)
        write_csv(commands_log_output_path, COMMANDS_LOG_HEADERS, commands_log_dicts)
        write_csv(feature_decision_output_path, FEATURE_DECISION_HEADERS, feature_decision_log_dicts)
        print("\nSimulation complete. Output files generated successfully.")
    except Exception as e:
        print(f"Error writing output files: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

