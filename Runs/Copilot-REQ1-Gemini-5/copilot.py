import argparse
import csv
import os
import collections
from enum import Enum, auto

class Copilot:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        self.state_log_path = os.path.join(output_dir, "state_log.csv")
        self.commands_log_path = os.path.join(output_dir, "commands_log.csv")
        self.feature_decision_path = os.path.join(output_dir, "feature_decision.csv")

        with open(self.state_log_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
        with open(self.commands_log_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "actuator_id", "values"])
        with open(self.feature_decision_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "feature", "decision"])

        self.current_state = CopilotState.DISENGAGED
        self.last_state_change_time = None
        self.attentiveness_check_due_time = None
        self.attentiveness_alarm_active = False
        self.alarm_command_issued = False # New flag to track if alarm ACTIVATE command has been issued

    def log_state_transition(self, timestamp, previous_state, current_state, trigger_event):
        if previous_state != current_state:
            with open(self.state_log_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, previous_state.name, current_state.name, trigger_event])

    def log_command(self, timestamp, actuator_id, values):
        with open(self.commands_log_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, actuator_id, values])

    def log_feature_decision(self, timestamp, feature, decision):
        with open(self.feature_decision_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, feature, decision])

    def process_event(self, event):
        timestamp = event['timestamp']
        event_type = event['type']

        previous_state = self.current_state

        # Emergency Braking (highest priority, always active)
        if event_type == 'sensor' and event['sensor_type'] == 'Lidar' and float(event['data_value']) < 5.0:
            self.log_command(timestamp, "Braking System", "BRAKE")
            self.log_feature_decision(timestamp, "emergency braking", "BRAKE")

        # Driver initiated disengagement (override all other states)
        if event_type == 'driver' and event['event_type'] == 'steering_wheel_force' and float(event['value']) > 10.0:
            if self.current_state != CopilotState.DISENGAGED:
                self.current_state = CopilotState.DISENGAGED
                self.log_state_transition(timestamp, previous_state, self.current_state, "driver_disengage_high_force")
                self.attentiveness_alarm_active = False # Reset alarm if disengaged
                self.alarm_command_issued = False # Reset alarm command flag
        else: # Only process other events if not disengaged by high steering force
            # State transitions based on driver events (engage/disengage)
            if event_type == 'driver' and event['event_type'] == 'copilot_switch':
                if event['value'] == 'engage' and self.current_state == CopilotState.DISENGAGED:
                    self.current_state = CopilotState.ENGAGED
                    self.log_state_transition(timestamp, previous_state, self.current_state, "driver_engage")
                    self.last_state_change_time = timestamp
                    self.attentiveness_check_due_time = timestamp + 120
                elif event['value'] == 'disengage' and self.current_state == CopilotState.ENGAGED:
                    self.current_state = CopilotState.DISENGAGED
                    self.log_state_transition(timestamp, previous_state, self.current_state, "driver_disengage_switch")
                    self.attentiveness_alarm_active = False # Reset alarm if disengaged
                    self.alarm_command_issued = False # Reset alarm command flag

            # Attentiveness check logic (only in ENGAGED state)
            if self.current_state == CopilotState.ENGAGED:
                if self.attentiveness_check_due_time and timestamp >= self.attentiveness_check_due_time and not self.attentiveness_alarm_active:
                    # Issue attentiveness prompt only if alarm is not already active
                    self.log_command(timestamp, "Steering System", "SMALL_MOVEMENT")
                    self.attentiveness_alarm_active = True
                    self.attentiveness_check_response_deadline = timestamp + 5

                if self.attentiveness_alarm_active and timestamp >= self.attentiveness_check_response_deadline and not self.alarm_command_issued:
                    # If no response within 5 seconds, emit alarm (only once)
                    self.log_command(timestamp, "Alarm System", "ACTIVATE")
                    self.alarm_command_issued = True

                # Handle driver response during an active alarm or after prompt but before deadline
                if event_type == 'driver' and event['event_type'] == 'steering_wheel_force' and self.attentiveness_alarm_active:
                    force = float(event['value'])
                    if timestamp <= self.attentiveness_check_response_deadline: # Driver responded within 5 seconds
                        if 0 < force <= 3.0:
                            self.attentiveness_alarm_active = False
                            self.alarm_command_issued = False # Reset alarm command flag
                            self.log_command(timestamp, "Alarm System", "DEACTIVATE")
                            self.attentiveness_check_due_time = timestamp + 120 # Reset timer
                        elif 3.0 < force <= 10.0:
                            # Ignore, continue waiting. Alarm remains active if deadline already passed.
                            pass
                    else: # Driver responded after 5 seconds (alarm was already active and potentially emitting)
                        self.attentiveness_alarm_active = False
                        self.alarm_command_issued = False # Reset alarm command flag
                        self.log_command(timestamp, "Alarm System", "DEACTIVATE")
                        self.attentiveness_check_due_time = timestamp + 120 # Reset timer


            # Other feature logic (Lane Keeping, Cruise Control) only if ENGAGED and no critical events
            if self.current_state == CopilotState.ENGAGED and not self.attentiveness_alarm_active:
                if event_type == 'sensor' and event['sensor_type'] == 'Camera':
                    # Dummy Lane Keeping logic
                    correction = 0.0 # Placeholder
                    self.log_command(timestamp, "Steering System", correction)
                    self.log_feature_decision(timestamp, "lane keeping", correction)
                elif event_type == 'sensor' and event['sensor_type'] == 'Lidar':
                    # Dummy Cruise Control logic
                    speed_adjustment = 0.0 # Placeholder
                    self.log_command(timestamp, "Engine Control", speed_adjustment)
                    self.log_feature_decision(timestamp, "cruise control", speed_adjustment)


class CopilotState(Enum):
    DISENGAGED = auto()
    ENGAGED = auto()


def read_csv_file(filepath, event_type_label):
    events = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            event = {'type': event_type_label}
            for key, value in row.items():
                if key == 'timestamp':
                    event[key] = float(value)
                elif key == 'data_value' or key == 'value':
                    try:
                        event[key] = float(value)
                    except ValueError: # Handle non-numeric values for 'value' (e.g., 'engage', 'disengage')
                        event[key] = value
                else:
                    event[key] = value
            events.append(event)
    return events

def main():
    parser = argparse.ArgumentParser(description="Simulate Copilot onboard computer.")
    parser.add_argument("--input", required=True, help="Directory containing input CSV files (sensor_log.csv, driver_events.csv).")
    parser.add_argument("--output", required=True, help="Directory where output CSV files will be written.")
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    sensor_log_path = os.path.join(input_dir, "sensor_log.csv")
    driver_events_path = os.path.join(input_dir, "driver_events.csv")

    all_events = []
    if os.path.exists(sensor_log_path):
        all_events.extend(read_csv_file(sensor_log_path, 'sensor'))
    if os.path.exists(driver_events_path):
        all_events.extend(read_csv_file(driver_events_path, 'driver'))

    all_events.sort(key=lambda x: x['timestamp'])

    copilot = Copilot(output_dir)

    for event in all_events:
        copilot.process_event(event)

if __name__ == "__main__":
    main()
