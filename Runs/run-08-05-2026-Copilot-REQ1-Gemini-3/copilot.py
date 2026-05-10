import argparse
import csv
import os
from datetime import datetime
from collections import deque

# Constants
LIDAR_EMERGENCY_DISTANCE = 5.0
ATTENTIVENESS_CHECK_INTERVAL = 120
ATTENTIVENESS_RESPONSE_WINDOW = 5
STEERING_FORCE_VALID = 3
STEERING_FORCE_IGNORED = 10

# States
STATE_DISENGAGED = "DISENGAGED"
STATE_ENGAGED = "ENGAGED"
STATE_ALARM = "ALARM"

# Event Types
EVENT_TYPE_SENSOR = "sensor"
EVENT_TYPE_DRIVER = "driver"

# Feature Decisions
FEATURE_CRUISE_CONTROL = "CRUISE_CONTROL"
FEATURE_EMERGENCY_BRAKING = "EMERGENCY_BRAKING"
FEATURE_LANE_KEEPING = "LANE_KEEPING"

class Copilot:
    def __init__(self, input_dir, output_dir):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.current_state = STATE_DISENGAGED
        self.last_state_transition_time = None # Not explicitly used for state logic yet, but good to keep
        self.last_attentiveness_check_time = None
        self.last_attentiveness_prompt_time = None # New: Timestamp when an attentiveness prompt was issued
        self.waiting_for_attentiveness_response = False # New: Flag to indicate if awaiting a response
        self.alarm_active = False # Keep as is, indicates if the ALARM state is currently active

        self._init_output_files()

    def _init_output_files(self):
        os.makedirs(self.output_dir, exist_ok=True)
        self.state_log_file = open(os.path.join(self.output_dir, "state_log.csv"), "w", newline="", encoding="utf-8")
        self.commands_log_file = open(os.path.join(self.output_dir, "commands_log.csv"), "w", newline="", encoding="utf-8")
        self.feature_decision_file = open(os.path.join(self.output_dir, "feature_decision.csv"), "w", newline="", encoding="utf-8")

        self.state_log_writer = csv.writer(self.state_log_file)
        self.commands_log_writer = csv.writer(self.commands_log_file)
        self.feature_decision_writer = csv.writer(self.feature_decision_file)

        self.state_log_writer.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
        self.commands_log_writer.writerow(["timestamp", "actuator_id", "values"])
        self.feature_decision_writer.writerow(["timestamp", "feature", "decision"])

    def _close_output_files(self):
        self.state_log_file.close()
        self.commands_log_file.close()
        self.feature_decision_file.close()

    def _log_state_transition(self, timestamp, previous_state, current_state, trigger_event):
        if previous_state != current_state:
            self.state_log_writer.writerow([timestamp, previous_state, current_state, trigger_event])
        self.current_state = current_state

    def _log_command(self, timestamp, actuator_id, values):
        self.commands_log_writer.writerow([timestamp, actuator_id, values])

    def _log_feature_decision(self, timestamp, feature, decision):
        self.feature_decision_writer.writerow([timestamp, feature, decision])

    def process_event(self, event_type, event_data):
        timestamp = event_data["timestamp"]
        original_state = self.current_state

        # Check for attentiveness timeout *before* processing the current event
        if self.current_state == STATE_ENGAGED and self.waiting_for_attentiveness_response and \
           (timestamp - self.last_attentiveness_prompt_time).total_seconds() > ATTENTIVENESS_RESPONSE_WINDOW:
            self._log_state_transition(timestamp, original_state, STATE_ALARM, "Attentiveness_Timeout")
            self.alarm_active = True
            self.waiting_for_attentiveness_response = False # No longer waiting, alarm is active
            original_state = STATE_ALARM # Update for subsequent checks in this event

        # Always check for steering force > 10N for immediate disengagement
        if event_type == EVENT_TYPE_DRIVER and event_data["event_type"] == "STEERING_WHEEL_FORCE" and float(event_data["value"]) > STEERING_FORCE_IGNORED:
            if self.current_state != STATE_DISENGAGED:
                self._log_state_transition(timestamp, original_state, STATE_DISENGAGED, "High_Steering_Force_Disengagement")
                self.alarm_active = False # Reset alarm on disengagement
                self.waiting_for_attentiveness_response = False # No longer waiting if disengaged
                self.last_attentiveness_prompt_time = None
            return

        # Emergency Braking (always active)
        if event_type == EVENT_TYPE_SENSOR and event_data["sensor_type"] == "LIDAR" and float(event_data["data_value"]) < LIDAR_EMERGENCY_DISTANCE:
            self._log_command(timestamp, "BRAKING_SYSTEM", "BRAKE")
            self._log_feature_decision(timestamp, FEATURE_EMERGENCY_BRAKING, "BRAKE")
            # Emergency braking doesn't change the mode, but acts as an override
            return

        # Process event based on current state
        if self.current_state == STATE_DISENGAGED:
            self._handle_disengaged_state(event_type, event_data)
        elif self.current_state == STATE_ENGAGED:
            self._handle_engaged_state(timestamp, event_type, event_data)
        elif self.current_state == STATE_ALARM:
            self._handle_alarm_state(timestamp, event_type, event_data)

    def _handle_disengaged_state(self, event_type, event_data):
        timestamp = event_data["timestamp"]
        if event_type == EVENT_TYPE_DRIVER and event_data["event_type"] == "ENGAGE_BUTTON_PRESS":
            self._log_state_transition(timestamp, STATE_DISENGAGED, STATE_ENGAGED, "Engage_Button_Press")
            self.last_attentiveness_check_time = timestamp # Start attentiveness timer
            self.last_state_transition_time = timestamp
            self.last_attentiveness_prompt_time = None # Reset prompt time
            self.waiting_for_attentiveness_response = False # Not waiting in new state

    def _handle_engaged_state(self, timestamp, event_type, event_data):
        # Attentiveness Check Prompt
        if not self.waiting_for_attentiveness_response and \
           self.last_attentiveness_check_time and \
           (timestamp - self.last_attentiveness_check_time).total_seconds() >= ATTENTIVENESS_CHECK_INTERVAL:
            self._log_command(timestamp, "STEERING_WHEEL", "SMALL_MOVEMENT")
            self.last_attentiveness_prompt_time = timestamp
            self.waiting_for_attentiveness_response = True
            # self.last_attentiveness_check_time is NOT reset here, it is reset only on a valid response or disengagement.

        if event_type == EVENT_TYPE_DRIVER:
            if event_data["event_type"] == "DISENGAGE_BUTTON_PRESS":
                self._log_state_transition(timestamp, STATE_ENGAGED, STATE_DISENGAGED, "Disengage_Button_Press")
                self.alarm_active = False
                self.waiting_for_attentiveness_response = False
                self.last_attentiveness_prompt_time = None
            elif event_data["event_type"] == "STEERING_WHEEL_FORCE" and self.waiting_for_attentiveness_response:
                force = float(event_data["value"])
                # Check if the force arrives within the attentiveness response window from the prompt time
                if (timestamp - self.last_attentiveness_prompt_time).total_seconds() <= ATTENTIVENESS_RESPONSE_WINDOW:
                    if force <= STEERING_FORCE_VALID:
                        # Valid response
                        self.last_attentiveness_check_time = timestamp # Reset 120s interval from response time
                        self.waiting_for_attentiveness_response = False
                        self.last_attentiveness_prompt_time = None
                        # Stay engaged
                    elif force > STEERING_FORCE_VALID and force <= STEERING_FORCE_IGNORED:
                        # Ignored, continue waiting for a valid response (still waiting_for_attentiveness_response = True)
                        pass
                # If force arrives too late, it's not a response to the attentiveness check
                # The attentiveness timeout would have already triggered ALARM or will trigger it.

        elif event_type == EVENT_TYPE_SENSOR:
            if event_data["sensor_type"] == "CAMERA":
                self._log_feature_decision(timestamp, FEATURE_LANE_KEEPING, "CORRECTION_VALUE_X")
                self._log_command(timestamp, "STEERING_SYSTEM", "CORRECTION_VALUE_X")
            elif event_data["sensor_type"] == "RADAR":
                self._log_feature_decision(timestamp, FEATURE_CRUISE_CONTROL, "ADJUST_SPEED_Y")
                self._log_command(timestamp, "ENGINE_CONTROL", "ADJUST_SPEED_Y")

    def _handle_alarm_state(self, timestamp, event_type, event_data):
        # While in ALARM state, it should maintain the alarm until driver responds.
        # It's assumed alarm is visually/audibly maintained by the system,
        # but here we only handle the state transition out of ALARM.
        if event_type == EVENT_TYPE_DRIVER and event_data["event_type"] == "STEERING_WHEEL_FORCE":
            force = float(event_data["value"])
            if force <= STEERING_FORCE_VALID:
                self._log_state_transition(timestamp, STATE_ALARM, STATE_ENGAGED, "Attentiveness_Response")
                self.alarm_active = False
                self.last_attentiveness_check_time = timestamp # Reset timer
                self.waiting_for_attentiveness_response = False
                self.last_attentiveness_prompt_time = None

class EventProcessor:
    def __init__(self, input_dir):
        self.sensor_log_path = os.path.join(input_dir, "sensor_log.csv")
        self.driver_events_path = os.path.join(input_dir, "driver_events.csv")
        self.events = deque()
        self._load_events()

    def _load_events(self):
        sensor_events = []
        driver_events = []

        with open(self.sensor_log_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["timestamp"] = datetime.fromisoformat(row["timestamp"])
                sensor_events.append((row["timestamp"], EVENT_TYPE_SENSOR, row))

        with open(self.driver_events_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["timestamp"] = datetime.fromisoformat(row["timestamp"])
                driver_events.append((row["timestamp"], EVENT_TYPE_DRIVER, row))

        all_events = sorted(sensor_events + driver_events, key=lambda x: x[0])
        self.events.extend(all_events)

    def get_next_event(self):
        if self.events:
            return self.events.popleft()
        return None

def main():
    parser = argparse.ArgumentParser(description="Simulate the Copilot driver-assistance system.")
    parser.add_argument("--input", type=str, required=True, help="Directory containing input CSV files.")
    parser.add_argument("--output", type=str, required=True, help="Directory to write output CSV files.")
    args = parser.parse_args()

    copilot = Copilot(args.input, args.output)
    event_processor = EventProcessor(args.input)

    while True:
        next_event = event_processor.get_next_event()
        if not next_event:
            break

        timestamp, event_type, event_data = next_event
        copilot.process_event(event_type, event_data)

    copilot._close_output_files()

if __name__ == "__main__":
    main()
