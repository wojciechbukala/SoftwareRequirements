import argparse
import csv
import os
import collections
from enum import Enum

# --- Constants and Enums ---

class SystemState(Enum):
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"

class SensorType(Enum):
    LIDAR = "Lidar"
    CAMERA = "Camera"

class DriverEventType(Enum):
    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"

class ActuatorID(Enum):
    BRAKING_SYSTEM = "BrakingSystem"
    STEERING_MOTOR = "SteeringMotor"
    SPEED_ACTUATOR = "SpeedActuator"
    ALARM_ACTUATOR = "AlarmActuator"

class Feature(Enum):
    EMERGENCY_BRAKING = "EmergencyBraking"
    LANE_KEEPING = "LaneKeeping"
    CRUISE_CONTROL = "CruiseControl"

# Time thresholds in seconds
ATTENTIVENESS_PROMPT_INTERVAL = 120.0
AWAITING_RESPONSE_WINDOW = 5.0

# Force thresholds in Newtons
DRIVER_RESPONSE_THRESHOLD = 3.0
DRIVER_OVERRIDE_THRESHOLD = 10.0

# Lidar distance for emergency braking in meters
EMERGENCY_BRAKING_DISTANCE = 5.0

# --- Helper Classes ---

Event = collections.namedtuple("Event", ["timestamp", "type", "data"])

class CSVWriter:
    def __init__(self, filepath, fieldnames):
        self.filepath = filepath
        self.fieldnames = fieldnames
        self.file = open(filepath, 'w', newline='', encoding='utf-8')
        self.writer = csv.DictWriter(self.file, fieldnames=fieldnames)
        self.writer.writeheader()

    def write_row(self, row):
        self.writer.writerow(row)

    def flush(self):
        self.file.flush()

    def close(self):
        self.file.close()

# --- Copilot System ---

class Copilot:
    def __init__(self, output_dir):
        self.state = SystemState.DISENGAGED
        self.last_attentiveness_prompt_time = 0.0
        self.awaiting_response_start_time = 0.0
        self.output_dir = output_dir

        self.state_log_writer = CSVWriter(
            os.path.join(output_dir, "state_log.csv"),
            ["timestamp", "previous_state", "current_state", "trigger_event"]
        )
        self.commands_log_writer = CSVWriter(
            os.path.join(output_dir, "commands_log.csv"),
            ["timestamp", "actuator_id", "values"]
        )
        self.feature_decision_writer = CSVWriter(
            os.path.join(output_dir, "feature_decision.csv"),
            ["timestamp", "feature", "decision"]
        )

    def _log_state_transition(self, timestamp, previous_state, current_state, trigger_event):
        if previous_state != current_state:
            print(f"[{timestamp:.2f}] STATE CHANGE: {previous_state.value} -> {current_state.value} ({trigger_event})")
            self.state_log_writer.write_row({
                "timestamp": timestamp,
                "previous_state": previous_state.value,
                "current_state": current_state.value,
                "trigger_event": trigger_event
            })
            self.state_log_writer.flush()

    def _log_command(self, timestamp, actuator_id, value):
        print(f"[{timestamp:.2f}] COMMAND: {actuator_id.value} -> {value}")
        self.commands_log_writer.write_row({
            "timestamp": timestamp,
            "actuator_id": actuator_id.value,
            "values": value
        })
        self.commands_log_writer.flush()

    def _log_feature_decision(self, timestamp, feature, decision):
        print(f"[{timestamp:.2f}] DECISION: {feature.value} -> {decision}")
        self.feature_decision_writer.write_row({
            "timestamp": timestamp,
            "feature": feature.value,
            "decision": decision
        })
        self.feature_decision_writer.flush()

    def _process_sensor_event(self, event):
        timestamp = event.timestamp
        sensor_type = event.data["sensor_type"]
        data_value = event.data["data_value"]

        print(f"[{timestamp:.2f}] Sensor Event: {sensor_type} - {data_value}")

        # Always evaluate emergency braking first, regardless of state
        if sensor_type == SensorType.LIDAR.value:
            if data_value < EMERGENCY_BRAKING_DISTANCE:
                self._log_feature_decision(timestamp, Feature.EMERGENCY_BRAKING, "BRAKE")
                self._log_command(timestamp, ActuatorID.BRAKING_SYSTEM, "APPLY_BRAKE")
                # When emergency braking is triggered, abandon other processing for this cycle.
                return
            else:
                self._log_feature_decision(timestamp, Feature.EMERGENCY_BRAKING, "NO_BRAKE")

        if self.state == SystemState.ENGAGED:
            if sensor_type == SensorType.CAMERA.value:
                # Placeholder for computing lane keeping and cruise control
                lane_keeping_correction = data_value * 0.1 # Example calculation
                cruise_control_adjustment = data_value * 0.05 # Example calculation

                self._log_feature_decision(timestamp, Feature.LANE_KEEPING, lane_keeping_correction)
                self._log_command(timestamp, ActuatorID.STEERING_MOTOR, lane_keeping_correction)

                self._log_feature_decision(timestamp, Feature.CRUISE_CONTROL, cruise_control_adjustment)
                self._log_command(timestamp, ActuatorID.SPEED_ACTUATOR, cruise_control_adjustment)
        elif self.state == SystemState.DISENGAGED:
            # Log data but no actuator commands or feature decisions for non-braking features
            pass # Already handled emergency braking logging.

    def _process_driver_event(self, event):
        timestamp = event.timestamp
        event_type = event.data["event_type"]
        value = event.data["value"]

        print(f"[{timestamp:.2f}] Driver Event: {event_type} - {value}")

        previous_state = self.state

        # FR-04: Driver Override (always takes precedence)
        if event_type == DriverEventType.STEERING_FORCE.value and value > DRIVER_OVERRIDE_THRESHOLD:
            self.state = SystemState.DISENGAGED
            self._log_state_transition(timestamp, previous_state, self.state, "DriverOverride (>10N)")
            return

        if self.state == SystemState.AWAITING_RESPONSE:
            if event_type == DriverEventType.STEERING_FORCE.value:
                if value <= DRIVER_RESPONSE_THRESHOLD:
                    self.state = SystemState.ENGAGED
                    self.last_attentiveness_prompt_time = timestamp # Reset timer
                    self._log_state_transition(timestamp, previous_state, self.state, "ValidDriverResponse (<=3N)")
                # else if value > DRIVER_RESPONSE_THRESHOLD and value <= DRIVER_OVERRIDE_THRESHOLD:
                #    Ignored, continue waiting. Handled by the 'return' above if it's an override.
            return # Don't process other driver events while awaiting response unless it's an override

        if self.state == SystemState.ALARMING:
            if event_type == DriverEventType.STEERING_FORCE.value and value <= DRIVER_RESPONSE_THRESHOLD:
                self.state = SystemState.ENGAGED
                self.last_attentiveness_prompt_time = timestamp # Reset timer
                self._log_state_transition(timestamp, previous_state, self.state, "DriverResponseFromAlarm (<=3N)")
            return # Don't process other driver events while alarming unless it's a valid response

        # Normal state transitions (Disengaged/Engaged)
        if event_type == DriverEventType.ENGAGE.value:
            if self.state == SystemState.DISENGAGED:
                self.state = SystemState.ENGAGED
                self.last_attentiveness_prompt_time = timestamp # Start timer
                self._log_state_transition(timestamp, previous_state, self.state, "ENGAGE_BUTTON")
        elif event_type == DriverEventType.DISENGAGE.value:
            if self.state == SystemState.ENGAGED:
                self.state = SystemState.DISENGAGED
                self._log_state_transition(timestamp, previous_state, self.state, "DISENGAGE_BUTTON")

    def _check_attentiveness(self, current_timestamp):
        previous_state = self.state
        if self.state == SystemState.ENGAGED:
            if current_timestamp - self.last_attentiveness_prompt_time >= ATTENTIVENESS_PROMPT_INTERVAL:
                self.state = SystemState.AWAITING_RESPONSE
                self.awaiting_response_start_time = current_timestamp
                self._log_command(current_timestamp, ActuatorID.STEERING_MOTOR, "SMALL_MOVEMENT")
                self._log_state_transition(current_timestamp, previous_state, self.state, "AttentivenessPrompt")
        elif self.state == SystemState.AWAITING_RESPONSE:
            if current_timestamp - self.awaiting_response_start_time >= AWAITING_RESPONSE_WINDOW:
                self.state = SystemState.ALARMING
                self._log_command(current_timestamp, ActuatorID.ALARM_ACTUATOR, "CONTINUOUS_ALARM")
                self._log_state_transition(current_timestamp, previous_state, self.state, "NoDriverResponse")

    def process_event(self, event):
        # First, check for attentiveness and transition if needed, before processing the current event
        self._check_attentiveness(event.timestamp)

        if event.type == "sensor":
            self._process_sensor_event(event)
        elif event.type == "driver":
            self._process_driver_event(event)

    def close_writers(self):
        self.state_log_writer.close()
        self.commands_log_writer.close()
        self.feature_decision_writer.close()

# --- Main Logic ---

def read_csv_events(filepath, event_type_prefix):
    events = []
    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp = float(row["timestamp"])
            data = {k: (float(v) if k in ["data_value", "value"] and v.replace('.', '', 1).isdigit() else v) for k, v in row.items() if k != "timestamp"}
            events.append(Event(timestamp, event_type_prefix, data))
    return events

def main():
    parser = argparse.ArgumentParser(description="Copilot driver-assistance system simulation.")
    parser.add_argument("--input", required=True, help="Path to the input directory containing sensor_log.csv and driver_events.csv.")
    parser.add_argument("--output", required=True, help="Path to the output directory for state_log.csv, commands_log.csv, and feature_decision.csv.")
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    os.makedirs(output_dir, exist_ok=True)

    sensor_log_path = os.path.join(input_dir, "sensor_log.csv")
    driver_events_path = os.path.join(input_dir, "driver_events.csv")

    all_events = []
    print(f"Reading sensor events from: {sensor_log_path}")
    all_events.extend(read_csv_events(sensor_log_path, "sensor"))
    print(f"Reading driver events from: {driver_events_path}")
    all_events.extend(read_csv_events(driver_events_path, "driver"))

    all_events.sort(key=lambda x: x.timestamp)

    copilot_system = Copilot(output_dir)

    print("--- Starting Copilot Simulation ---")
    for event in all_events:
        copilot_system.process_event(event)
    print("--- Copilot Simulation Finished ---")

    copilot_system.close_writers()

if __name__ == "__main__":
    main()
