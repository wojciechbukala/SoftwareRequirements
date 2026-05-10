"""
Copilot driver-assistance system simulation.

This script simulates the logic of an onboard computer for advanced driver assistance,
processing sensor data and driver events to manage autonomous driving states,
emergency braking, and driver attentiveness.
"""
import argparse
import csv
from datetime import datetime
from enum import Enum

class SystemState(Enum):
    """
    Represents the possible states of the Copilot system.
    """
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"

class SensorType(Enum):
    """
    Represents the types of sensors.
    """
    LIDAR = "Lidar"
    CAMERA = "Camera"

class DriverEventType(Enum):
    """
    Represents the types of driver events.
    """
    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"

class Copilot:
    """
    Simulates the Copilot driver-assistance system.
    """
    def __init__(self):
        self.state = SystemState.DISENGAGED
        self.last_prompt_time = None
        self.awaiting_response_start_time = None

        self.state_log = []
        self.commands_log = []
        self.feature_decision_log = []

    def _log_state_transition(self, timestamp, previous_state, current_state, trigger_event):
        """
        Records a state transition if the state has actually changed.
        """
        if previous_state != current_state:
            self.state_log.append({
                "timestamp": timestamp,
                "previous_state": previous_state.value,
                "current_state": current_state.value,
                "trigger_event": trigger_event
            })

    def _log_command(self, timestamp, actuator_id, values):
        """
        Records an actuator command.
        """
        self.commands_log.append({
            "timestamp": timestamp,
            "actuator_id": actuator_id,
            "values": values
        })

    def _log_feature_decision(self, timestamp, feature, decision):
        """
        Records a feature decision.
        """
        self.feature_decision_log.append({
            "timestamp": timestamp,
            "feature": feature,
            "decision": decision
        })

    def handle_sensor_event(self, event):
        """
        Handles incoming sensor events (PF-01).
        """
        timestamp = event["timestamp"]
        sensor_type = event["sensor_type"]
        data_value = float(event["data_value"])

        # FR-02, PF-01: Emergency braking (Lidar) - always active
        if sensor_type == SensorType.LIDAR.value:
            if data_value < 5.0:
                self._log_feature_decision(timestamp, "EmergencyBraking", "Triggered")
                self._log_command(timestamp, "BrakingSystem", "APPLY_BRAKE")
                # According to FR-02, abandon other processing if braking is triggered
                return
            else:
                self._log_feature_decision(timestamp, "EmergencyBraking", "NotTriggered")
        else: # sensor_type != LIDAR.value
            # FR-02, PF-01: Other sensor events only take action when in Engaged mode
            if self.state == SystemState.ENGAGED:
                if sensor_type == SensorType.CAMERA.value:
                    # Placeholder for actual computation based on data_value
                    lane_keeping_correction = f"CORRECT_STEERING_{data_value * 0.1:.2f}"
                    cruise_control_adjustment = f"ADJUST_SPEED_{data_value * 0.05:.2f}"

                    self._log_command(timestamp, "SteeringMotor", lane_keeping_correction)
                    self._log_command(timestamp, "SpeedActuator", cruise_control_adjustment)
                    self._log_feature_decision(timestamp, "LaneKeeping", lane_keeping_correction)
                    self._log_feature_decision(
                        timestamp, "CruiseControl", cruise_control_adjustment)
            elif self.state == SystemState.DISENGAGED: # Disengaged mode: log, no actions
                self._log_feature_decision(timestamp, "LaneKeeping", "Ignored")
                self._log_feature_decision(timestamp, "CruiseControl", "Ignored")
            # For AWAITING_RESPONSE and ALARMING, do nothing for non-Lidar sensor events


    def handle_driver_event(self, event):
        """
        Handles incoming driver events (FR-01, FR-03, FR-04).
        """
        timestamp = event["timestamp"]
        event_type = event["event_type"]
        value = float(event["value"]) if "value" in event else None

        previous_state = self.state

        # FR-04: Driver Override
        if event_type == DriverEventType.STEERING_FORCE.value and value > 10.0:
            self.state = SystemState.DISENGAGED
            self.last_prompt_time = None # Reset attentiveness timer
            self.awaiting_response_start_time = None
            self._log_state_transition(
                timestamp, previous_state, self.state, "DriverOverride_HighForce")
            return

        if event_type == DriverEventType.ENGAGE.value:
            if self.state == SystemState.DISENGAGED:
                self.state = SystemState.ENGAGED
                self.last_prompt_time = timestamp # Start attentiveness timer
                self._log_state_transition(timestamp, previous_state, self.state, "DriverEngage")
        elif event_type == DriverEventType.DISENGAGE.value:
            if self.state != SystemState.DISENGAGED:
                self.state = SystemState.DISENGAGED
                self.last_prompt_time = None # Reset attentiveness timer
                self.awaiting_response_start_time = None
                self._log_state_transition(timestamp, previous_state, self.state, "DriverDisengage")
        elif event_type == DriverEventType.STEERING_FORCE.value:
            if self.state == SystemState.AWAITING_RESPONSE:
                if value <= 3.0: # Valid response
                    self.state = SystemState.ENGAGED
                    self.last_prompt_time = timestamp # Reset attentiveness timer
                    self.awaiting_response_start_time = None
                    self._log_state_transition(
                        timestamp, previous_state, self.state,
                        "AttentivenessResponse_Valid")
                elif 3.0 < value <= 10.0: # Ignored response
                    # Do nothing, continue waiting
                    pass
            elif self.state == SystemState.ALARMING:
                if value <= 3.0: # Escape alarming
                    self.state = SystemState.ENGAGED
                    self.last_prompt_time = timestamp # Reset attentiveness timer
                    self.awaiting_response_start_time = None
                    self._log_state_transition(
                        timestamp, previous_state, self.state,
                        "AlarmEscape_ValidResponse")

    def check_attentiveness(self, current_timestamp):
        """
        Checks for attentiveness prompts and responses (FR-03).
        """
        previous_state = self.state

        if self.state == SystemState.ENGAGED:
            if self.last_prompt_time and \
               ((current_timestamp - self.last_prompt_time).total_seconds() >= 120):
                self.state = SystemState.AWAITING_RESPONSE
                self.awaiting_response_start_time = current_timestamp
                self._log_command(current_timestamp, "SteeringMotor", "SMALL_MOVEMENT_PROMPT")
                self._log_state_transition(
                    current_timestamp, previous_state, self.state, "AttentivenessPrompt")
        elif self.state == SystemState.AWAITING_RESPONSE:
            if self.awaiting_response_start_time and \
               ((current_timestamp - self.awaiting_response_start_time).total_seconds() >= 5):
                self.state = SystemState.ALARMING
                self._log_command(
                    current_timestamp, "AlarmActuator", "CONTINUOUS_ALARM")
                self.awaiting_response_start_time = None # End awaiting response period
                self._log_state_transition(
                    current_timestamp, previous_state, self.state, "AttentivenessTimeout")


def parse_arguments():
    """
    Parses command-line arguments for input and output directories.
    """
    parser = argparse.ArgumentParser(description="Copilot driver-assistance system simulation.")
    parser.add_argument(
        "--input", required=True,
        help="Path to the input directory containing CSV files.")
    parser.add_argument(
        "--output", required=True,
        help="Path to the output directory for generated CSV logs.")
    return parser.parse_args()

def read_csv_file(filepath):
    """
    Reads a CSV file and returns its content as a list of dictionaries.
    """
    data = []
    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

def write_csv_file(filepath, data, fieldnames):
    """
    Writes data to a CSV file.
    """
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

def main():
    """
    Main function to run the Copilot simulation.
    """
    args = parse_arguments()
    input_dir = args.input
    output_dir = args.output

    # Read input files
    sensor_events_raw = read_csv_file(f"{input_dir}/sensor_log.csv")
    driver_events_raw = read_csv_file(f"{input_dir}/driver_events.csv")

    # Convert timestamps and merge events
    all_events = []
    for event in sensor_events_raw:
        event["timestamp"] = datetime.fromisoformat(event["timestamp"])
        event["type"] = "sensor"
        all_events.append(event)
    for event in driver_events_raw:
        event["timestamp"] = datetime.fromisoformat(event["timestamp"])
        event["type"] = "driver"
        all_events.append(event)

    # Sort all events by timestamp
    all_events.sort(key=lambda x: x["timestamp"])

    copilot = Copilot()
    for event in all_events:
        print(f"Processing event at {event['timestamp']}: Type={event['type']}, Current State={copilot.state.value}")
        copilot.check_attentiveness(event["timestamp"]) # Check attentiveness before processing current event

        if event["type"] == "sensor":
            copilot.handle_sensor_event(event)
        elif event["type"] == "driver":
            copilot.handle_driver_event(event)

    # Write output files
    state_log_fieldnames = ["timestamp", "previous_state", "current_state", "trigger_event"]
    write_csv_file(
        f"{output_dir}/state_log.csv",
        copilot.state_log,
        state_log_fieldnames)
    commands_log_fieldnames = ["timestamp", "actuator_id", "values"]
    write_csv_file(
        f"{output_dir}/commands_log.csv",
        copilot.commands_log,
        commands_log_fieldnames)
    feature_decision_fieldnames = ["timestamp", "feature", "decision"]
    write_csv_file(
        f"{output_dir}/feature_decision_log.csv",
        copilot.feature_decision_log,
        feature_decision_fieldnames)

    print("Simulation finished. Output logs generated.")

if __name__ == "__main__":
    main()
