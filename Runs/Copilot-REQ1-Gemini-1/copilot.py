import argparse
import csv
import os
import collections

# Define system states
STATE_DISENGAGED = "DISENGAGED"
STATE_ENGAGED = "ENGAGED"
STATE_ATTENTIVENESS_PENDING = "ATTENTIVENESS_PENDING"

# Output file headers
STATE_LOG_HEADERS = ["timestamp", "previous_state", "current_state", "trigger_event"]
COMMANDS_LOG_HEADERS = ["timestamp", "actuator_id", "values"]
FEATURE_DECISION_HEADERS = ["timestamp", "feature", "decision"]

# Constants for attentiveness check
ATTENTIVENESS_INTERVAL = 120.0  # seconds
ATTENTIVENESS_WAIT_TIME = 5.0  # seconds
STEERING_FORCE_VALID_THRESHOLD = 3.0  # N
STEERING_FORCE_DISENGAGE_THRESHOLD = 10.0  # N
LIDAR_EMERGENCY_BRAKING_THRESHOLD = 5.0  # meters

class CopilotSystem:
    def __init__(self, output_dir):
        self.current_state = STATE_DISENGAGED
        self.last_attentiveness_prompt_timestamp = 0.0

        # Output file paths
        self.state_log_path = os.path.join(output_dir, "state_log.csv")
        self.commands_log_path = os.path.join(output_dir, "commands_log.csv")
        self.feature_decision_path = os.path.join(output_dir, "feature_decision.csv")

        # Open CSV writers
        self.state_log_file = open(self.state_log_path, 'w', newline='', encoding='utf-8')
        self.commands_log_file = open(self.commands_log_path, 'w', newline='', encoding='utf-8')
        self.feature_decision_file = open(self.feature_decision_path, 'w', newline='', encoding='utf-8')

        self.state_log_writer = csv.writer(self.state_log_file)
        self.commands_log_writer = csv.writer(self.commands_log_file)
        self.feature_decision_writer = csv.writer(self.feature_decision_file)

        self.state_log_writer.writerow(STATE_LOG_HEADERS)
        self.commands_log_writer.writerow(COMMANDS_LOG_HEADERS)
        self.feature_decision_writer.writerow(FEATURE_DECISION_HEADERS)

    def _log_state_transition(self, timestamp, previous_state, current_state, trigger_event):
        if previous_state != current_state:
            self.state_log_writer.writerow([timestamp, previous_state, current_state, trigger_event])

    def _log_command(self, timestamp, actuator_id, values):
        self.commands_log_writer.writerow([timestamp, actuator_id, values])

    def _log_feature_decision(self, timestamp, feature, decision):
        self.feature_decision_writer.writerow([timestamp, feature, decision])

    def _handle_emergency_braking(self, timestamp, data_value):
        # Emergency braking is always active
        if data_value < LIDAR_EMERGENCY_BRAKING_THRESHOLD:
            self._log_command(timestamp, "Braking System", "BRAKE")
            self._log_feature_decision(timestamp, "emergency braking", "BRAKE")
            return True
        else:
            self._log_feature_decision(timestamp, "emergency braking", "NO_BRAKE")
            return False

    def _handle_attentiveness_check(self, timestamp, event_type, value):
        if self.current_state == STATE_ENGAGED:
            if timestamp - self.last_attentiveness_prompt_timestamp >= ATTENTIVENESS_INTERVAL:
                self._log_command(timestamp, "Steering Wheel", "SMALL_MOVEMENT")
                self.last_attentiveness_prompt_timestamp = timestamp
                self.attentiveness_wait_timer = timestamp  # Start waiting for response
                self._transition_state(timestamp, STATE_ATTENTIVENESS_PENDING, "Attentiveness Prompt")
                self.alarm_active = False # Ensure alarm is off when prompt is issued
        
        elif self.current_state == STATE_ATTENTIVENESS_PENDING:
            if event_type == "steering_wheel_force":
                if value <= STEERING_FORCE_VALID_THRESHOLD:
                    # Valid response
                    if self.alarm_active:
                        self._log_command(timestamp, "Alarm System", "DEACTIVATE")
                        self.alarm_active = False
                    self._transition_state(timestamp, STATE_ENGAGED, "Attentiveness Response Valid")
                    self.last_attentiveness_prompt_timestamp = timestamp # Reset 120s timer
                    self.attentiveness_wait_timer = 0.0 # Reset wait timer
                elif value > STEERING_FORCE_VALID_THRESHOLD and value < STEERING_FORCE_DISENGAGE_THRESHOLD:
                    # Ignored, continue waiting for valid response
                    pass
            
            # Check for timeout and activate alarm if no valid response
            if timestamp - self.attentiveness_wait_timer >= ATTENTIVENESS_WAIT_TIME and not self.alarm_active:
                self._log_command(timestamp, "Alarm System", "ACTIVATE")
                self.alarm_active = True
                
    def _transition_state(self, timestamp, new_state, trigger_event):
        previous_state = self.current_state
        if previous_state != new_state: # Only log if state actually changes
            self.current_state = new_state
            self._log_state_transition(timestamp, previous_state, self.current_state, trigger_event)

    def process_event(self, event):
        timestamp = event['timestamp']
        event_type = event.get('event_type')
        sensor_type = event.get('sensor_type')
        data_value = event.get('data_value')
        value = event.get('value')

        # Handle disengagement due to high steering force at any time
        if event_type == "steering_wheel_force" and value is not None and value > STEERING_FORCE_DISENGAGE_THRESHOLD:
            if self.current_state != STATE_DISENGAGED: # Ensure we only transition if not already disengaged
                if self.alarm_active:
                    self._log_command(timestamp, "Alarm System", "DEACTIVATE")
                    self.alarm_active = False
                self._transition_state(timestamp, STATE_DISENGAGED, "High Steering Force")
                self.last_attentiveness_prompt_timestamp = 0.0 # Reset timers
                self.attentiveness_wait_timer = 0.0
            return # No further processing if disengaged by force

        # Emergency braking check (always active for Lidar readings)
        if sensor_type == "Lidar":
            self._handle_emergency_braking(timestamp, data_value)

        # Attentiveness check and handling
        self._handle_attentiveness_check(timestamp, event_type, value)

        # State transitions based on driver events
        if event_type == "driver_engage" and self.current_state == STATE_DISENGAGED:
            self._transition_state(timestamp, STATE_ENGAGED, "Driver Engage")
            self.last_attentiveness_prompt_timestamp = timestamp # Start attentiveness timer
            self.attentiveness_wait_timer = 0.0 # Reset wait timer
        elif event_type == "driver_disengage" and (self.current_state == STATE_ENGAGED or self.current_state == STATE_ATTENTIVENESS_PENDING):
            if self.alarm_active:
                self._log_command(timestamp, "Alarm System", "DEACTIVATE")
                self.alarm_active = False
            self._transition_state(timestamp, STATE_DISENGAGED, "Driver Disengage")
            self.last_attentiveness_prompt_timestamp = 0.0 # Reset timers
            self.attentiveness_wait_timer = 0.0

        # Logic for engaged mode (lane keeping, cruise control)
        if self.current_state == STATE_ENGAGED:
            if sensor_type == "Camera":
                self._log_command(timestamp, "Steering System", "ADJUST_LANE")
                self._log_feature_decision(timestamp, "lane keeping", "ADJUST_LANE")
            elif sensor_type == "Radar":
                self._log_command(timestamp, "Engine Control", "ADJUST_SPEED")
                self._log_feature_decision(timestamp, "cruise control", "ADJUST_SPEED")
        elif self.current_state == STATE_DISENGAGED or self.current_state == STATE_ATTENTIVENESS_PENDING:
            # When disengaged or pending attentiveness, these features are inactive (except emergency braking)
            if sensor_type == "Camera":
                self._log_feature_decision(timestamp, "lane keeping", "INACTIVE")
            elif sensor_type == "Radar":
                self._log_feature_decision(timestamp, "cruise control", "INACTIVE")


    def close(self):
        self.state_log_file.close()
        self.commands_log_file.close()
        self.feature_decision_file.close()


def read_sensor_log(file_path):
    events = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['timestamp'] = float(row['timestamp'])
            row['data_value'] = float(row['data_value'])
            row['event_type'] = "sensor_reading" # Add a generic event type for sorting
            events.append(row)
    return events

def read_driver_events(file_path):
    events = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['timestamp'] = float(row['timestamp'])
            if 'value' in row and row['value']: # 'value' might be empty for some event types
                row['value'] = float(row['value'])
            events.append(row)
    return events

def main():
    parser = argparse.ArgumentParser(description="Simulate the Copilot driver-assistance system.")
    parser.add_argument("--input", required=True, help="Directory containing input CSV files (sensor_log.csv, driver_events.csv).")
    parser.add_argument("--output", required=True, help="Directory where output CSV files will be written (state_log.csv, commands_log.csv, feature_decision.csv).")
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    sensor_log_path = os.path.join(input_dir, "sensor_log.csv")
    driver_events_path = os.path.join(input_dir, "driver_events.csv")

    all_events = []
    all_events.extend(read_sensor_log(sensor_log_path))
    all_events.extend(read_driver_events(driver_events_path))

    # Sort all events by timestamp
    all_events.sort(key=lambda x: x['timestamp'])

    copilot = CopilotSystem(output_dir)

    for event in all_events:
        copilot.process_event(event)
    
    # Final check for attentiveness alarm if still pending when no more events
    # This might be tricky if the simulation ends exactly during a wait period.
    # For now, let's assume events will cover critical timing or system is shut down.

    copilot.close()

if __name__ == "__main__":
    main()
