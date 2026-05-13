import argparse
import os
import sys
from typing import List, Union

from copilot_logic import CopilotSystem
from copilot_csv_handler import read_sensor_log, read_driver_events, 
    write_state_log, write_commands_log, write_feature_decision_log, 
    SensorEventData, DriverEventData

def main():
    """
    Main function for the Copilot CLI application.
    Parses arguments, processes events, and writes output logs.
    """
    parser = argparse.ArgumentParser(description="Copilot: Advanced Driver Assistance System Simulation.")
    parser.add_argument("--input", required=True, help="Path to the input directory containing sensor_log.csv and driver_events.csv.")
    parser.add_argument("--output", required=True, help="Path to the output directory for state_log.csv, commands_log.csv, and feature_decision.csv.")

    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    # Validate input directory
    if not os.path.isdir(input_dir):
        print(f"Error: Input directory '{input_dir}' not found.", file=sys.stderr)
        sys.exit(1)

    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: '{output_dir}'")
    elif not os.path.isdir(output_dir):
        print(f"Error: Output path '{output_dir}' exists but is not a directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Reading input from: {input_dir}")
    print(f"Writing output to: {output_dir}")

    # Read input files
    sensor_log_path = os.path.join(input_dir, "sensor_log.csv")
    driver_events_path = os.path.join(input_dir, "driver_events.csv")

    sensor_events: List[SensorEventData] = read_sensor_log(sensor_log_path)
    driver_events: List[DriverEventData] = read_driver_events(driver_events_path)

    all_events: List[Union[SensorEventData, DriverEventData]] = []
    all_events.extend(sensor_events)
    all_events.extend(driver_events)

    if not all_events:
        print("No events found in input files. Exiting.", file=sys.stderr)
        sys.exit(0)

    print(f"Total events read: {len(all_events)}")

    # Initialize and run Copilot system
    copilot = CopilotSystem()
    print("Processing events...")
    copilot.process_all_events(all_events)
    print("Event processing complete.")

    # Write output logs
    state_log_output_path = os.path.join(output_dir, "state_log.csv")
    commands_log_output_path = os.path.join(output_dir, "commands_log.csv")
    feature_decision_output_path = os.path.join(output_dir, "feature_decision.csv")

    write_state_log(state_log_output_path, copilot.state_log)
    write_commands_log(commands_log_output_path, copilot.commands_log)
    write_feature_decision_log(feature_decision_output_path, copilot.feature_decision_log)

    print(f"Output written to: {output_dir}")
    print("Copilot simulation finished successfully.")

if __name__ == "__main__":
    main()
