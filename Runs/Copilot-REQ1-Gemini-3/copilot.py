import argparse
import csv
import os
from enum import Enum, auto

class CopilotState(Enum):
    DISENGAGED = auto()
    ENGAGED = auto()
    ATTENTIVENESS_CHECK_PENDING = auto()
    ALARMING = auto()

class Copilot:
    def __init__(self, input_dir, output_dir):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.current_state = CopilotState.DISENGAGED
        self.last_state_change_timestamp = 0.0

        os.makedirs(output_dir, exist_ok=True)
        self.state_log_file = open(os.path.join(output_dir, "state_log.csv"), 'w', newline='', encoding='utf-8')
        self.commands_log_file = open(os.path.join(output_dir, "commands_log.csv"), 'w', newline='', encoding='utf-8')
        self.feature_decision_file = open(os.path.join(output_dir, "feature_decision.csv"), 'w', newline='', encoding='utf-8')

        self.state_logger = csv.writer(self.state_log_file)
        self.commands_logger = csv.writer(self.commands_log_file)
        self.feature_decision_logger = csv.writer(self.feature_decision_file)

        self.state_logger.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
        self.commands_logger.writerow(["timestamp", "actuator_id", "values"])
        self.feature_decision_logger.writerow(["timestamp", "feature", "decision"])

        self.last_attentiveness_prompt_time = 0.0
        self.attentiveness_check_issued = False
        self.alarm_active = False

    def __del__(self):
        self.state_log_file.close()
        self.commands_log_file.close()
        self.feature_decision_file.close()

    def log_state_transition(self, timestamp, previous_state, current_state, trigger_event):
        if previous_state != current_state:
            self.state_logger.writerow([timestamp, previous_state.name, current_state.name, trigger_event])

    def issue_command(self, timestamp, actuator_id, values):
        self.commands_logger.writerow([timestamp, actuator_id, values])

    def record_feature_decision(self, timestamp, feature, decision):
        self.feature_decision_logger.writerow([timestamp, feature, decision])



    def process_event(self, event_type, timestamp, sensor_id=None, sensor_type=None, data_value=None, unit=None, driver_event_type=None, value=None):
        previous_state = self.current_state
        trigger_event = driver_event_type if driver_event_type else event_type # Use specific driver event type if available

        # 1. Emergency Braking (highest priority, always active)
        if sensor_type == "Lidar" and data_value is not None and data_value < 5.0:
            self.issue_command(timestamp, "Braking System", "BRAKE")
            self.record_feature_decision(timestamp, "emergency braking", "BRAKE")
            # Emergency braking does not change the core state of engagement unless driver input intervenes later.

        # 2. Driver initiated disengagement by strong steering (global priority)
        if driver_event_type == "Steering" and value is not None and value > 10.0:
            if self.current_state != CopilotState.DISENGAGED:
                self.current_state = CopilotState.DISENGAGED
                # Only log the state change once for this event
                self.log_state_transition(timestamp, previous_state, self.current_state, "StrongSteeringDisengage")
                self.attentiveness_check_issued = False
                self.alarm_active = False
                # If alarm was active, deactivate it
                if previous_state == CopilotState.ALARMING:
                    self.issue_command(timestamp, "Alarm System", "DEACTIVATE")
                return # This event fully handles the state and potentially overrides other processing

        # 3. Handle global "Engage" and "Disengage" driver events
        if driver_event_type == "Engage":
            if self.current_state == CopilotState.DISENGAGED:
                self.current_state = CopilotState.ENGAGED
                self.log_state_transition(timestamp, previous_state, self.current_state, "Engage")
                self.last_attentiveness_prompt_time = timestamp # Reset timer on engage
                self.attentiveness_check_issued = False # Ensure no pending check
                self.alarm_active = False # Ensure no active alarm
                return
            elif self.current_state in [CopilotState.ATTENTIVENESS_CHECK_PENDING, CopilotState.ALARMING]:
                # If driver re-engages, it cancels attentiveness check/alarm
                self.current_state = CopilotState.ENGAGED
                self.log_state_transition(timestamp, previous_state, self.current_state, "EngageDuringAttentiveness")
                self.last_attentiveness_prompt_time = timestamp
                self.attentiveness_check_issued = False
                self.alarm_active = False
                self.issue_command(timestamp, "Alarm System", "DEACTIVATE") # Deactivate if it was active
                return

        if driver_event_type == "Disengage":
            if self.current_state != CopilotState.DISENGAGED:
                self.current_state = CopilotState.DISENGAGED
                self.log_state_transition(timestamp, previous_state, self.current_state, "Disengage")
                self.attentiveness_check_issued = False
                self.alarm_active = False
                if previous_state == CopilotState.ALARMING:
                    self.issue_command(timestamp, "Alarm System", "DEACTIVATE")
                return

        # 4. State-specific logic
        if self.current_state == CopilotState.DISENGAGED:
            # Only emergency braking is active, already handled above.
            # Other sensor data is logged but no commands issued for lane keeping/cruise control
            pass
        
        elif self.current_state == CopilotState.ENGAGED:
            # Attentiveness prompt logic
            if not self.attentiveness_check_issued and (timestamp - self.last_attentiveness_prompt_time) >= 120.0:
                self.issue_command(timestamp, "Steering System", "SMALL_MOVEMENT")
                self.record_feature_decision(timestamp, "attentiveness check", "PROMPT")
                self.last_attentiveness_prompt_time = timestamp # This is the start time for the 5s window
                self.attentiveness_check_issued = True
                self.current_state = CopilotState.ATTENTIVENESS_CHECK_PENDING
                self.log_state_transition(timestamp, previous_state, self.current_state, "AttentivenessPrompt")
                # No further processing for this event, as state has changed

            # If still engaged, process sensor data for active features
            elif event_type == "sensor_reading":
                if sensor_type == "Camera":
                    self.record_feature_decision(timestamp, "lane keeping", "CORRECT_LANE")
                    self.issue_command(timestamp, "Steering System", "LANE_CORRECTION_VALUE") # Placeholder
                elif sensor_type == "Lidar":
                    # Beyond emergency braking, Lidar might be used for cruise control adjustments
                    self.record_feature_decision(timestamp, "cruise control", "ADJUST_SPEED")
                    self.issue_command(timestamp, "Accelerator System", "SPEED_ADJUSTMENT_VALUE") # Placeholder
        
        elif self.current_state == CopilotState.ATTENTIVENESS_CHECK_PENDING:
            # Check for attentiveness timeout
            if (timestamp - self.last_attentiveness_prompt_time) > 5.0 and not self.alarm_active:
                self.issue_command(timestamp, "Alarm System", "ACTIVATE")
                self.alarm_active = True
                self.current_state = CopilotState.ALARMING
                self.log_state_transition(timestamp, previous_state, self.current_state, "AttentivenessTimeout")
                # No further processing for this event, as state has changed

            # Handle driver response if it's a Steering event
            elif driver_event_type == "Steering" and value is not None:
                if value <= 3.0: # Valid response
                    self.current_state = CopilotState.ENGAGED
                    self.log_state_transition(timestamp, previous_state, self.current_state, "AttentivenessResponse")
                    self.last_attentiveness_prompt_time = timestamp # Reset 120s timer
                    self.attentiveness_check_issued = False
                    self.alarm_active = False
                    # No command to deactivate alarm here, as it wouldn't have been active yet in this state
                elif 3.0 < value < 10.0: # Ignored response
                    pass # Continue waiting, state remains ATTENTIVENESS_CHECK_PENDING
                # value > 10.0 handled by global disengagement logic

        elif self.current_state == CopilotState.ALARMING:
            # Alarm is active, waiting for any valid driver response
            if driver_event_type == "Steering" and value is not None:
                if value <= 3.0: # Valid response
                    self.current_state = CopilotState.ENGAGED
                    self.log_state_transition(timestamp, previous_state, self.current_state, "AlarmResponse")
                    self.last_attentiveness_prompt_time = timestamp
                    self.attentiveness_check_issued = False
                    self.alarm_active = False
                    self.issue_command(timestamp, "Alarm System", "DEACTIVATE")
                elif 3.0 < value < 10.0: # Ignored response
                    pass # Continue alarming, state remains ALARMING
                # value > 10.0 handled by global disengagement logic



def parse_args():
    parser = argparse.ArgumentParser(description="Simulate the Copilot driver-assistance system.")
    parser.add_argument("--input", required=True, help="Directory containing input CSV files (sensor_log.csv, driver_events.csv).")
    parser.add_argument("--output", required=True, help="Directory where output CSV files will be written (state_log.csv, commands_log.csv, feature_decision.csv).")
    return parser.parse_args()

def read_csv_events(filepath, event_type_name):
    events = []
    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['timestamp'] = float(row['timestamp'])
            row['event_type_name'] = event_type_name # Custom field to differentiate source
            events.append(row)
    return events

def main():
    args = parse_args()

    copilot = Copilot(args.input, args.output)

    sensor_events = read_csv_events(os.path.join(args.input, "sensor_log.csv"), "sensor_reading")
    driver_events = read_csv_events(os.path.join(args.input, "driver_events.csv"), "driver_event")

    all_events = sorted(sensor_events + driver_events, key=lambda x: x['timestamp'])

    for event in all_events:
        event_type_name = event['event_type_name']
        timestamp = event['timestamp']

        if event_type_name == "sensor_reading":
            copilot.process_event(
                event_type=event_type_name,
                timestamp=timestamp,
                sensor_id=event['sensor_id'],
                sensor_type=event['sensor_type'],
                data_value=float(event['data_value']),
                unit=event['unit']
            )
        elif event_type_name == "driver_event":
            # Assuming 'value' is present and can be converted to float for driver events
            # Need to handle cases where 'value' might be a string (e.g., 'Engage', 'Disengage')
            # For simplicity, if value is numeric, convert to float, otherwise pass as string
            try:
                event_value = float(event['value'])
            except ValueError:
                event_value = event['value']

            copilot.process_event(
                event_type=event_type_name,
                timestamp=timestamp,
                driver_event_type=event['event_type'], # Pass specific driver event type
                value=event_value
            )

if __name__ == "__main__":
    main()
