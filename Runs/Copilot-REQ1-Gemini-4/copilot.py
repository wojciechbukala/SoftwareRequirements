import argparse
import csv
import heapq
import os
from collections import deque

# Constants
STATE_DISENGAGED = "DISENGAGED"
STATE_ENGAGED = "ENGAGED"

ATTENTIVENESS_CHECK_INTERVAL = 120.0
ATTENTIVENESS_RESPONSE_WINDOW = 5.0
STEERING_FORCE_DISENGAGE_THRESHOLD = 10.0
STEERING_FORCE_VALID_RESPONSE_THRESHOLD = 3.0
EMERGENCY_BRAKING_DISTANCE_THRESHOLD = 5.0

# Output file headers
STATE_LOG_HEADERS = ["timestamp", "previous_state", "current_state", "trigger_event"]
COMMANDS_LOG_HEADERS = ["timestamp", "actuator_id", "values"]
FEATURE_DECISION_HEADERS = ["timestamp", "feature", "decision"]

class Copilot:
    def __init__(self, input_dir, output_dir):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.current_state = STATE_DISENGAGED
        self.last_state_change_event = None
        self.attentiveness_timer = 0.0
        self.attentiveness_check_active = False
        self.attentiveness_check_start_time = 0.0
        self.alarm_active = False
        self.last_valid_attentiveness_response_time = 0.0

        # Output file paths
        self.state_log_path = os.path.join(output_dir, "state_log.csv")
        self.commands_log_path = os.path.join(output_dir, "commands_log.csv")
        self.feature_decision_path = os.path.join(output_dir, "feature_decision.csv")

        # Initialize output files
        self._write_csv_headers(self.state_log_path, STATE_LOG_HEADERS)
        self._write_csv_headers(self.commands_log_path, COMMANDS_LOG_HEADERS)
        self._write_csv_headers(self.feature_decision_path, FEATURE_DECISION_HEADERS)

    def _write_csv_headers(self, file_path, headers):
        os.makedirs(self.output_dir, exist_ok=True)
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    def _log_state_transition(self, timestamp, previous_state, current_state, trigger_event):
        if previous_state != current_state:
            with open(self.state_log_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, previous_state, current_state, trigger_event])

    def _log_command(self, timestamp, actuator_id, values):
        with open(self.commands_log_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, actuator_id, values])

    def _log_feature_decision(self, timestamp, feature, decision):
        with open(self.feature_decision_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, feature, decision])

    def _read_sensor_log(self):
        sensor_log_path = os.path.join(self.input_dir, "sensor_log.csv")
        events = []
        with open(sensor_log_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    events.append({
                        "timestamp": float(row["timestamp"]),
                        "type": "sensor",
                        "sensor_id": row["sensor_id"],
                        "sensor_type": row["sensor_type"],
                        "data_value": float(row["data_value"]),
                        "unit": row["unit"]
                    })
                except ValueError as e:
                    print(f"Skipping malformed sensor event row: {row} - {e}")
        return events

    def _read_driver_events(self):
        driver_events_path = os.path.join(self.input_dir, "driver_events.csv")
        events = []
        with open(driver_events_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    events.append({
                        "timestamp": float(row["timestamp"]),
                        "type": "driver",
                        "event_type": row["event_type"],
                        "value": float(row["value"])
                    })
                except ValueError as e:
                    print(f"Skipping malformed driver event row: {row} - {e}")
        return events

    def _process_event(self, event):
        timestamp = event["timestamp"]
        previous_state = self.current_state
        trigger_event_str = f"{event['type']}:{event.get('sensor_type', event.get('event_type'))}"

        # Check for immediate disengagement due to high steering force
        if event["type"] == "driver" and event["event_type"] == "Steering Wheel Force" and event["value"] > STEERING_FORCE_DISENGAGE_THRESHOLD:
            if self.current_state == STATE_ENGAGED: # Disengage only if currently engaged
                self.current_state = STATE_DISENGAGED
                self.attentiveness_check_active = False
                self.alarm_active = False
                self._log_state_transition(timestamp, previous_state, self.current_state, "Driver:Steering Wheel Force > 10N")
            self.attentiveness_timer = timestamp # Reset timer on any strong steering input
            self.last_valid_attentiveness_response_time = timestamp
            return # Event handled, stop further processing for this event

        # Emergency Braking (highest priority, always active)
        if event["type"] == "sensor" and event["sensor_type"] == "Lidar" and event["data_value"] < EMERGENCY_BRAKING_DISTANCE_THRESHOLD:
            self._log_command(timestamp, "Braking System", "BRAKE")
            self._log_feature_decision(timestamp, "emergency braking", "BRAKE")

        # Attentiveness Check (Engaged mode only)
        if self.current_state == STATE_ENGAGED:
            # Handle attentiveness check timeout and alarm
            if self.attentiveness_check_active and (timestamp - self.attentiveness_check_start_time) >= ATTENTIVENESS_RESPONSE_WINDOW and not self.alarm_active:
                self._log_command(timestamp, "Alarm System", "ACTIVATE")
                self.alarm_active = True
                self._log_feature_decision(timestamp, "attentiveness", "ALARM")

            # Issue attentiveness prompt if interval passed
            if (timestamp - self.attentiveness_timer) >= ATTENTIVENESS_CHECK_INTERVAL and not self.attentiveness_check_active:
                self._log_command(timestamp, "Steering Wheel Actuator", "SMALL_MOVEMENT")
                self._log_feature_decision(timestamp, "attentiveness", "PROMPT")
                self.attentiveness_check_active = True
                self.attentiveness_check_start_time = timestamp
                self.alarm_active = False # Reset alarm if it was active and a new prompt is issued

            if event["type"] == "driver" and event["event_type"] == "Steering Wheel Force" and self.attentiveness_check_active:
                force = event["value"]
                if force <= STEERING_FORCE_VALID_RESPONSE_THRESHOLD:
                    # Valid response
                    self.attentiveness_check_active = False
                    self.alarm_active = False
                    self.attentiveness_timer = timestamp # Restart timer from valid response
                    self.last_valid_attentiveness_response_time = timestamp
                    self._log_feature_decision(timestamp, "attentiveness", "VALID_RESPONSE")
                elif force > STEERING_FORCE_VALID_RESPONSE_THRESHOLD and force < STEERING_FORCE_DISENGAGE_THRESHOLD:
                    # Ignored response, continue waiting
                    self._log_feature_decision(timestamp, "attentiveness", "IGNORED_RESPONSE")
                    pass # Do nothing, continue waiting
                # High force (>10N) already handled for disengagement at the beginning of the function

        # State transitions based on driver events (Engage/Disengage)
        if event["type"] == "driver" and event["event_type"] == "Button Press":
            if event["value"] == 1.0 and self.current_state == STATE_DISENGAGED: # Engage button
                self.current_state = STATE_ENGAGED
                self.attentiveness_timer = timestamp # Start attentiveness timer on engagement
                self.last_valid_attentiveness_response_time = timestamp
                self._log_state_transition(timestamp, previous_state, self.current_state, "Driver:Button Press:Engage")
            elif event["value"] == 0.0 and self.current_state == STATE_ENGAGED: # Disengage button
                self.current_state = STATE_DISENGAGED
                self.attentiveness_check_active = False
                self.alarm_active = False
                self._log_state_transition(timestamp, previous_state, self.current_state, "Driver:Button Press:Disengage")

        # In Engaged mode, issue commands for Lane Keeping and Cruise Control
        if self.current_state == STATE_ENGAGED:
            if event["type"] == "sensor":
                if event["sensor_type"] == "Camera":
                    # Example: Lane Keeping
                    self._log_command(timestamp, "Steering System", f"ADJUST_LANE:{event['data_value']}")
                    self._log_feature_decision(timestamp, "lane keeping", event["data_value"])
                elif event["sensor_type"] == "Radar":
                    # Example: Cruise Control
                    self._log_command(timestamp, "Engine Control", f"ADJUST_SPEED:{event['data_value']}")
                    self._log_feature_decision(timestamp, "cruise control", event["data_value"])
        
        # In disengaged mode, log sensor data but do not issue commands for lane keeping or cruise control.
        # Emergency braking is handled earlier and is always active.

    def run(self):
        sensor_events = self._read_sensor_log()
        driver_events = self._read_driver_events()

        # Merge and sort all events by timestamp
        all_events = heapq.merge(sensor_events, driver_events, key=lambda x: x["timestamp"])

        for event in all_events:
            self._process_event(event)

def main():
    parser = argparse.ArgumentParser(description="Simulates the Copilot onboard computer for a driver-assistance system.")
    parser.add_argument("--input", required=True, help="Directory containing input CSV files (sensor_log.csv, driver_events.csv).")
    parser.add_argument("--output", required=True, help="Directory where output CSV files (state_log.csv, commands_log.csv, feature_decision.csv) will be written.")
    args = parser.parse_args()

    copilot = Copilot(args.input, args.output)
    copilot.run()

if __name__ == "__main__":
    main()
