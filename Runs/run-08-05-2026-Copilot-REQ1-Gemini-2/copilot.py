import argparse
import csv
from datetime import datetime

class Copilot:
    DISENGAGED = "disengaged"
    ENGAGED = "engaged"

    def __init__(self, input_dir, output_dir):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.current_state = self.DISENGAGED
        self.state_log = []
        self.commands_log = []
        self.feature_decision_log = []
        self.last_attentiveness_check_time = None
        self.attentiveness_alarm_active = False

    def _log_state_transition(self, timestamp, previous_state, current_state, trigger_event):
        if previous_state != current_state:
            self.state_log.append({
                "timestamp": timestamp,
                "previous_state": previous_state,
                "current_state": current_state,
                "trigger_event": trigger_event
            })

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

    def process_events(self):
        sensor_log_path = f"{self.input_dir}/sensor_log.csv"
        driver_events_path = f"{self.input_dir}/driver_events.csv"

        all_events = self._read_and_merge_events(sensor_log_path, driver_events_path)
        
        for event in all_events:
            timestamp = event["timestamp"]
            event_type = event["event_type"]
            value = event.get("value") # Driver events have 'value', sensor events have 'data_value'

            previous_state = self.current_state

            # Emergency braking is always active
            if event_type == "Lidar" and float(event["data_value"]) < 5.0:
                self._log_command(timestamp, "Braking System", "BRAKE")
                self._log_feature_decision(timestamp, "emergency braking", "BRAKE")

            # Driver events
            if event_type == "driver_event":
                if value == "engage":
                    self.current_state = self.ENGAGED
                    self.last_attentiveness_check_time = timestamp # Reset timer on engagement
                elif value == "disengage" or (event["event_type"] == "steering_wheel_force" and float(value) > 10.0):
                    self.current_state = self.DISENGAGED
                    self.attentiveness_alarm_active = False # Reset alarm on disengagement

            # Attentiveness check (only in engaged mode)
            if self.current_state == self.ENGAGED:
                if self.last_attentiveness_check_time is not None and 
                   (timestamp - self.last_attentiveness_check_time).total_seconds() >= 120 and 
                   not self.attentiveness_alarm_active:
                    
                    self._log_command(timestamp, "Steering Wheel", "SMALL_MOVEMENT")
                    self.attentiveness_alarm_active = True
                    # The next state is waiting for response, but the current_state remains ENGAGED.
                    # This internal state 'attentiveness_alarm_active' helps manage the logic.
                
                if self.attentiveness_alarm_active and event_type == "driver_event" and event["event_type"] == "steering_wheel_force":
                    force = float(value)
                    if force <= 3.0:
                        self.last_attentiveness_check_time = timestamp # Restart timer
                        self.attentiveness_alarm_active = False
                    elif 3.0 < force <= 10.0:
                        # Ignore, continue waiting
                        pass
                    # If force > 10.0, disengagement handled above.

            # Lane keeping and cruise control (only in engaged mode)
            if self.current_state == self.ENGAGED:
                if event_type == "Camera":
                    # Placeholder for actual lane keeping logic
                    # Assuming some 'correction_value' from camera data
                    correction_value = float(event["data_value"]) * 0.1 # Example
                    self._log_command(timestamp, "Steering System", f"ADJUST_STEERING:{correction_value}")
                    self._log_feature_decision(timestamp, "lane keeping", f"correction:{correction_value}")
                elif event_type == "Radar":
                    # Placeholder for actual cruise control logic
                    # Assuming some 'speed_adjustment' from radar data
                    speed_adjustment = float(event["data_value"]) * 0.05 # Example
                    self._log_command(timestamp, "Engine Control Unit", f"ADJUST_SPEED:{speed_adjustment}")
                    self._log_feature_decision(timestamp, "cruise control", f"adjustment:{speed_adjustment}")
            
            self._log_state_transition(timestamp, previous_state, self.current_state, event_type)

        self._write_output_files()


    def _read_and_merge_events(self, sensor_log_path, driver_events_path):
        all_events = []

        # Read sensor log
        with open(sensor_log_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["timestamp"] = datetime.fromisoformat(row["timestamp"])
                row["event_type"] = row["sensor_type"] # Use sensor_type as event_type for sorting
                all_events.append(row)

        # Read driver events
        with open(driver_events_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["timestamp"] = datetime.fromisoformat(row["timestamp"])
                row["event_type"] = "driver_event" # Differentiate driver events
                all_events.append(row)

        # Sort all events by timestamp
        all_events.sort(key=lambda x: x["timestamp"])
        return all_events

    def _write_output_files(self):
        # state_log.csv
        with open(f"{self.output_dir}/state_log.csv", mode='w', newline='', encoding='utf-8') as f:
            fieldnames = ["timestamp", "previous_state", "current_state", "trigger_event"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.state_log:
                # Format timestamp back to string for output
                row["timestamp"] = row["timestamp"].isoformat()
                writer.writerow(row)

        # commands_log.csv
        with open(f"{self.output_dir}/commands_log.csv", mode='w', newline='', encoding='utf-8') as f:
            fieldnames = ["timestamp", "actuator_id", "values"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.commands_log:
                row["timestamp"] = row["timestamp"].isoformat()
                writer.writerow(row)

        # feature_decision.csv
        with open(f"{self.output_dir}/feature_decision.csv", mode='w', newline='', encoding='utf-8') as f:
            fieldnames = ["timestamp", "feature", "decision"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.feature_decision_log:
                row["timestamp"] = row["timestamp"].isoformat()
                writer.writerow(row)

def main():
    parser = argparse.ArgumentParser(description="Simulate the Copilot driver-assistance system.")
    parser.add_argument("--input", required=True, help="Directory containing input CSV files.")
    parser.add_argument("--output", required=True, help="Directory to write output CSV files.")
    args = parser.parse_args()

    copilot = Copilot(args.input, args.output)
    copilot.process_events()

if __name__ == "__main__":
    main()
