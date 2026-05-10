import argparse
import csv
from datetime import datetime
import os
import time

class Copilot:
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"

    ATTENTIVENESS_PROMPT_INTERVAL_SECONDS = 120
    AWAITING_RESPONSE_TIMEOUT_SECONDS = 5
    VALID_RESPONSE_STEERING_FORCE_N = 3
    IGNORE_STEERING_FORCE_N = 10

    def __init__(self, output_dir):
        self.state = self.DISENGAGED
        self.output_dir = output_dir
        self.state_log = []
        self.commands_log = []
        self.feature_decision_log = []
        self.last_attentiveness_prompt_time = None
        self.attentiveness_timeout_start_time = None
        self.last_event_timestamp = 0.0

        self._ensure_output_dir_exists()
        self._write_output_headers()

    def _ensure_output_dir_exists(self):
        os.makedirs(self.output_dir, exist_ok=True)

    def _write_output_headers(self):
        with open(os.path.join(self.output_dir, "state_log.csv"), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
        with open(os.path.join(self.output_dir, "commands_log.csv"), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "actuator_id", "values"])
        with open(os.path.join(self.output_dir, "feature_decision.csv"), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "feature", "decision"])

    def _log_state_transition(self, timestamp, previous_state, current_state, trigger_event):
        if previous_state != current_state:
            self.state_log.append([timestamp, previous_state, current_state, trigger_event])

    def _log_command(self, timestamp, actuator_id, value):
        self.commands_log.append([timestamp, actuator_id, value])

    def _log_feature_decision(self, timestamp, feature, decision):
        self.feature_decision_log.append([timestamp, feature, decision])

    def _set_state(self, timestamp, new_state, trigger_event=""):
        if self.state != new_state:
            self._log_state_transition(timestamp, self.state, new_state, trigger_event)
            self.state = new_state
            print(f"[{timestamp:.3f}] State changed to {self.state} due to {trigger_event}")

    def process_event(self, event):
        timestamp = event["timestamp"]
        self.last_event_timestamp = timestamp

        # Check for driver override first (FR-04)
        if event["type"] == "driver" and event["event_type"] == "STEERING_FORCE" and event["value"] > self.IGNORE_STEERING_FORCE_N:
            print(f"[{timestamp:.3f}] Driver override detected (STEERING_FORCE > 10N). Transitioning to Disengaged.")
            self._set_state(timestamp, self.DISENGAGED, "Driver Override")
            # Reset attentiveness timer on disengage
            self.last_attentiveness_prompt_time = None
            self.attentiveness_timeout_start_time = None
            return

        # Attentiveness check and timeout handling (FR-03)
        if self.state == self.AWAITING_RESPONSE:
            if timestamp - self.attentiveness_timeout_start_time >= self.AWAITING_RESPONSE_TIMEOUT_SECONDS:
                print(f"[{timestamp:.3f}] Attentiveness response timed out. Transitioning to Alarming.")
                self._set_state(timestamp, self.ALARMING, "Attentiveness Timeout")
                self._log_command(timestamp, "Alarm Actuator", "CONTINUOUS_ALARM")
            elif event["type"] == "driver" and event["event_type"] == "STEERING_FORCE" and event["value"] <= self.VALID_RESPONSE_STEERING_FORCE_N:
                print(f"[{timestamp:.3f}] Valid attentiveness response received. Transitioning back to Engaged.")
                self._set_state(timestamp, self.ENGAGED, "Valid Attentiveness Response")
                self.last_attentiveness_prompt_time = timestamp # Reset timer
                self.attentiveness_timeout_start_time = None
            elif event["type"] == "driver" and event["event_type"] == "STEERING_FORCE" and self.VALID_RESPONSE_STEERING_FORCE_N < event["value"] <= self.IGNORE_STEERING_FORCE_N:
                print(f"[{timestamp:.3f}] Steering force {event['value']}N ignored in AwaitingResponse state.")
                # System continues waiting, do nothing.

        elif self.state == self.ALARMING:
            if event["type"] == "driver" and event["event_type"] == "STEERING_FORCE" and event["value"] <= self.VALID_RESPONSE_STEERING_FORCE_N:
                print(f"[{timestamp:.3f}] Valid response in Alarming state. Transitioning to Engaged.")
                self._set_state(timestamp, self.ENGAGED, "Alarm Dismissed by Driver")
                self.last_attentiveness_prompt_time = timestamp # Reset timer
                self.attentiveness_timeout_start_time = None
                # Stop alarm command? Requirements don't explicitly state. Assuming it stops automatically when state changes.

        # Process driver events (Engage/Disengage)
        if event["type"] == "driver":
            if event["event_type"] == "ENGAGE":
                if self.state != self.ENGAGED:
                    print(f"[{timestamp:.3f}] Driver ENGAGE event. Transitioning to Engaged.")
                    self._set_state(timestamp, self.ENGAGED, "Driver ENGAGE")
                    self.last_attentiveness_prompt_time = timestamp
                else:
                    print(f"[{timestamp:.3f}] Driver ENGAGE event ignored, already in Engaged state.")
            elif event["event_type"] == "DISENGAGE":
                if self.state != self.DISENGAGED:
                    print(f"[{timestamp:.3f}] Driver DISENGAGE event. Transitioning to Disengaged.")
                    self._set_state(timestamp, self.DISENGAGED, "Driver DISENGAGE")
                    self.last_attentiveness_prompt_time = None
                    self.attentiveness_timeout_start_time = None
                else:
                    print(f"[{timestamp:.3f}] Driver DISENGAGE event ignored, already in Disengaged state.")
            # Steering force events already handled above for override/attentiveness

        # Process sensor events
        elif event["type"] == "sensor":
            if event["sensor_type"] == "Lidar":
                # Emergency braking is always active (FR-02, PF-01)
                distance = event["data_value"]
                if distance < 5.0:
                    print(f"[{timestamp:.3f}] Lidar < 5m ({distance}m). Emergency braking triggered.")
                    self._log_feature_decision(timestamp, "Emergency Braking", "BRAKE")
                    self._log_command(timestamp, "Braking System Actuator", "BRAKE")
                else:
                    self._log_feature_decision(timestamp, "Emergency Braking", "NO_BRAKE")

            # Only process other sensor events if engaged and not in AWAITING_RESPONSE/ALARMING due to a timeout that already passed in the current event loop iteration
            if self.state == self.ENGAGED:
                if event["sensor_type"] == "Camera":
                    # Assume data_value is correction, unit is adjustment based on requirements description
                    lane_keeping_correction = event["data_value"]
                    cruise_control_adjustment = event.get("data_value_2", 0.0) # Assuming a second data_value for cruise control or a default

                    print(f"[{timestamp:.3f}] Camera event in Engaged mode. Lane Keeping & Cruise Control.")
                    self._log_feature_decision(timestamp, "Lane Keeping", lane_keeping_correction)
                    self._log_command(timestamp, "Steering Motor Actuator", lane_keeping_correction)
                    
                    self._log_feature_decision(timestamp, "Cruise Control", cruise_control_adjustment)
                    self._log_command(timestamp, "Speed Actuator", cruise_control_adjustment)
                # If Lidar triggered emergency braking, other features are abandoned for this cycle.
                # The _log_feature_decision and _log_command are called only once for Lidar,
                # then for Camera if the state is ENGAGED. This logic respects the priority.

        # Attentiveness prompt (FR-03)
        if self.state == self.ENGAGED and self.last_attentiveness_prompt_time is not None:
            if (timestamp - self.last_attentiveness_prompt_time) >= self.ATTENTIVENESS_PROMPT_INTERVAL_SECONDS:
                print(f"[{timestamp:.3f}] Attentiveness prompt issued. Transitioning to AwaitingResponse.")
                self._set_state(timestamp, self.AWAITING_RESPONSE, "Attentiveness Prompt")
                self._log_command(timestamp, "Steering Wheel Actuator", "SMALL_MOVEMENT")
                self.attentiveness_timeout_start_time = timestamp

    def flush_logs(self):
        with open(os.path.join(self.output_dir, "state_log.csv"), 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(self.state_log)
        with open(os.path.join(self.output_dir, "commands_log.csv"), 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(self.commands_log)
        with open(os.path.join(self.output_dir, "feature_decision.csv"), 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(self.feature_decision_log)

def read_events_from_csv(file_path, event_type):
    events = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            event = {"type": event_type, "timestamp": float(row["timestamp"])}
            if event_type == "sensor":
                event["sensor_id"] = row["sensor_id"]
                event["sensor_type"] = row["sensor_type"]
                event["data_value"] = float(row["data_value"])
                event["unit"] = row["unit"]
                # Special handling for Camera events, assuming "data_value_2" if present for cruise control
                if row["sensor_type"] == "Camera" and "data_value_2" in row:
                    event["data_value_2"] = float(row["data_value_2"])
            elif event_type == "driver":
                event["event_type"] = row["event_type"]
                # Value might not be present for ENGAGE/DISENGAGE
                event["value"] = float(row["value"]) if "value" in row and row["value"] else 0.0
            events.append(event)
    return events

def main():
    parser = argparse.ArgumentParser(description="Copilot driver-assistance system simulation.")
    parser.add_argument("--input", required=True, help="Path to the input directory containing sensor_log.csv and driver_events.csv.")
    parser.add_argument("--output", required=True, help="Path to the output directory for state_log.csv, commands_log.csv, and feature_decision.csv.")
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    sensor_log_path = os.path.join(input_dir, "sensor_log.csv")
    driver_events_path = os.path.join(input_dir, "driver_events.csv")

    if not os.path.exists(sensor_log_path):
        print(f"Error: sensor_log.csv not found at {sensor_log_path}")
        return
    if not os.path.exists(driver_events_path):
        print(f"Error: driver_events.csv not found at {driver_events_path}")
        return

    copilot = Copilot(output_dir)

    sensor_events = read_events_from_csv(sensor_log_path, "sensor")
    driver_events = read_events_from_csv(driver_events_path, "driver")

    all_events = sorted(sensor_events + driver_events, key=lambda x: x["timestamp"])

    print("Starting Copilot simulation...")
    for event in all_events:
        copilot.process_event(event)
    print("Simulation finished. Flushing logs...")
    copilot.flush_logs()
    print("Logs flushed successfully.")

if __name__ == "__main__":
    main()
