import argparse
import os
import csv
from datetime import datetime, timedelta

class Copilot:
    def __init__(self, input_dir, output_dir):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.current_state = "DISENGAGED"  # Initial state
        # Attentiveness check attributes
        self._last_attentiveness_prompt_timestamp = None
        self._attentiveness_alarm_active = False
        self._attentiveness_timeout_expected = None


        # Output data lists
        self.state_log = []
        self.commands_log = []
        self.feature_decision_log = []

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

    def _log_state_transition(self, timestamp, previous_state, current_state, trigger_event):
        if previous_state != current_state:
            self.state_log.append({
                "timestamp": timestamp,
                "previous_state": previous_state,
                "current_state": current_state,
                "trigger_event": trigger_event
            })
            self.last_state_transition_timestamp = timestamp

    def _log_command(self, timestamp, actuator_id, values):
        self.commands_log.append({
            "timestamp": timestamp,
            "actuator_id": actuator_id,
            "values": values
        })

    def _log_feature_decision(self, timestamp, feature, decision):
        self.feature_decision_log.append({
            "timestamp": timestamp,
            "feature": feature,
            "decision": decision
        })

    def _process_sensor_event(self, event):
        timestamp = event['timestamp']
        sensor_type = event['sensor_type']
        data_value = event['data_value']

        # Emergency braking logic (always active)
        if sensor_type == 'Lidar' and float(data_value) < 5.0:
            self._log_command(timestamp, "Braking System", "BRAKE")
            self._log_feature_decision(timestamp, "emergency_braking", "BRAKE")

        if self.current_state == "ENGAGED":
            # Lane keeping and cruise control (simplified for now)
            if sensor_type == 'Camera':
                self._log_feature_decision(timestamp, "lane_keeping", "ACTIVE")
            if sensor_type == 'Radar': # Assuming Radar for cruise control, not specified in detail
                self._log_feature_decision(timestamp, "cruise_control", "ACTIVE")

    def _process_driver_event(self, event):
        timestamp = event['timestamp']
        event_type = event['event_type']
        value = event['value']

        previous_state = self.current_state

        # Disengagement due to high steering force (always active)
        if event_type == 'steering_force' and float(value) > 10.0:
            self.current_state = "DISENGAGED"
            self._log_state_transition(timestamp, previous_state, self.current_state, event_type)
            # Reset attentiveness timers/alarms
            self._last_attentiveness_prompt_timestamp = None
            self._attentiveness_alarm_active = False
            self._attentiveness_timeout_expected = None
            return

        if self.current_state == "ENGAGED":
            # Attentiveness check logic
            if event_type == 'steering_force': # This event type also covers attentiveness responses
                steering_force = float(value)
                current_timestamp_dt = datetime.fromisoformat(timestamp)

                # Check if it's a valid response to an active prompt
                if (steering_force <= 3.0 and 
                    self._attentiveness_timeout_expected is not None and
                    current_timestamp_dt <= self._attentiveness_timeout_expected):
                    
                    # Valid response, restart 120s interval
                    self._last_attentiveness_prompt_timestamp = current_timestamp_dt
                    self._attentiveness_timeout_expected = None
                    if self._attentiveness_alarm_active:
                        self._log_command(timestamp, "Alarm System", "DEACTIVATE")
                        self._attentiveness_alarm_active = False
                elif steering_force > 3.0 and steering_force < 10.0:
                    # Ignored response, continue waiting, alarm (if active) persists
                    pass
                # steering_force > 10.0 is handled at the beginning of the function

        # Driver engagement/disengagement
        if event_type == 'toggle_engagement':
            if value == 'ENGAGE' and self.current_state == "DISENGAGED":
                self.current_state = "ENGAGED"
                self._log_state_transition(timestamp, previous_state, self.current_state, event_type)
            elif value == 'DISENGAGE' and self.current_state == "ENGAGED":
                self.current_state = "DISENGAGED"
                self._log_state_transition(timestamp, previous_state, self.current_state, event_type)

    def run(self):
        self._read_input_files()
        self._merge_and_sort_events()

        for event in self.event_stream:
            current_timestamp_dt = event['timestamp_dt']
            
            # --- Attentiveness Check Logic (executed at each event) ---
            if self.current_state == "ENGAGED":
                # Check if it's time to issue an attentiveness prompt
                if (self._last_attentiveness_prompt_timestamp is None or
                    (current_timestamp_dt - self._last_attentiveness_prompt_timestamp).total_seconds() >= 120):
                    
                    # Issue prompt command
                    self._log_command(current_timestamp_dt.isoformat(), "Steering Wheel Actuator", "SMALL_MOVEMENT")
                    self._last_attentiveness_prompt_timestamp = current_timestamp_dt
                    self._attentiveness_timeout_expected = current_timestamp_dt + timedelta(seconds=5)
                    self._attentiveness_alarm_active = False # Reset alarm state on new prompt

                # Check for attentiveness timeout
                if (self._attentiveness_timeout_expected is not None and
                    current_timestamp_dt > self._attentiveness_timeout_expected and
                    not self._attentiveness_alarm_active):
                    
                    # No response within 5 seconds, activate alarm
                    self._log_command(current_timestamp_dt.isoformat(), "Alarm System", "ACTIVATE")
                    self._attentiveness_alarm_active = True
            elif self.current_state == "DISENGAGED":
                # Reset attentiveness timers/alarms when disengaged
                self._last_attentiveness_prompt_timestamp = None
                self._attentiveness_alarm_active = False
                self._attentiveness_timeout_expected = None


            if event['type'] == 'sensor':
                self._process_sensor_event(event)
            elif event['type'] == 'driver':
                self._process_driver_event(event)

        self._write_output_files()

    def _read_input_files(self):
        # Read sensor_log.csv
        sensor_log_path = os.path.join(self.input_dir, "sensor_log.csv")
        if os.path.exists(sensor_log_path):
            with open(sensor_log_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row['type'] = 'sensor'
                    self.event_stream.append(row)
        else:
            print(f"Warning: {sensor_log_path} not found.")

        # Read driver_events.csv
        driver_events_path = os.path.join(self.input_dir, "driver_events.csv")
        if os.path.exists(driver_events_path):
            with open(driver_events_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row['type'] = 'driver'
                    self.event_stream.append(row)
        else:
            print(f"Warning: {driver_events_path} not found.")

    def _merge_and_sort_events(self):
        # Convert timestamp to datetime objects for proper sorting
        for event in self.event_stream:
            event['timestamp_dt'] = datetime.fromisoformat(event['timestamp']) # Assuming ISO format for simplicity

        self.event_stream.sort(key=lambda x: x['timestamp_dt'])

    def _write_output_files(self):
        # Write state_log.csv
        if self.state_log:
            with open(os.path.join(self.output_dir, "state_log.csv"), 'w', newline='', encoding='utf-8') as f:
                fieldnames = ["timestamp", "previous_state", "current_state", "trigger_event"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.state_log)

        # Write commands_log.csv
        if self.commands_log:
            with open(os.path.join(self.output_dir, "commands_log.csv"), 'w', newline='', encoding='utf-8') as f:
                fieldnames = ["timestamp", "actuator_id", "values"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.commands_log)

        # Write feature_decision.csv
        if self.feature_decision_log:
            with open(os.path.join(self.output_dir, "feature_decision.csv"), 'w', newline='', encoding='utf-8') as f:
                fieldnames = ["timestamp", "feature", "decision"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.feature_decision_log)

def main():
    parser = argparse.ArgumentParser(description="Simulate the Copilot driver-assistance system.")
    parser.add_argument("--input", required=True, help="Directory containing input CSV files (sensor_log.csv, driver_events.csv).")
    parser.add_argument("--output", required=True, help="Directory where output CSV files (state_log.csv, commands_log.csv, feature_decision.csv) will be written.")
    args = parser.parse_args()

    copilot = Copilot(args.input, args.output)
    copilot.run()

if __name__ == "__main__":
    main()
