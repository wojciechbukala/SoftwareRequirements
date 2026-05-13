import argparse
import os
import csv
from datetime import datetime
from enum import Enum

class State(Enum):
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"

class Copilot:
    def __init__(self, csv_manager):
        self.csv_manager = csv_manager
        self.current_state = State.DISENGAGED
        self.last_attentiveness_prompt_time = 0
        self.awaiting_response_start_time = 0

    def _transition_state(self, new_state, timestamp, trigger_event=""):
        if self.current_state != new_state:
            self.csv_manager.append_state_log(timestamp, self.current_state.value, new_state.value, trigger_event)
            self.current_state = new_state
            print(f"[{timestamp}] State transition: {self.current_state.value} -> {new_state.value} (Trigger: {trigger_event})")
            return True
        return False

    def process_event(self, event):
        timestamp = event['timestamp']
        event_type = event['type']

        # Driver Override check (highest priority)
        if event_type == 'driver' and event['event_type'] == 'STEERING_FORCE' and int(event['value']) > 10:
            self._transition_state(State.DISENGAGED, timestamp, "Driver Override (Steering Force > 10N)")
            return

        # Emergency Braking (second highest priority, always active)
        if event_type == 'sensor' and event['sensor_type'] == 'Lidar' and int(event['data_value']) < 5:
            self.csv_manager.append_feature_decision(timestamp, "Emergency Braking", "Brake")
            self.csv_manager.append_commands_log(timestamp, "Braking System", "APPLY_BRAKE")
            print(f"[{timestamp}] Emergency Braking triggered!")
            return # Skip other processing for this cycle if emergency braking

        # Process events based on current state
        if self.current_state == State.DISENGAGED:
            self._handle_disengaged_state(event)
        elif self.current_state == State.ENGAGED:
            self._handle_engaged_state(event)
        elif self.current_state == State.AWAITING_RESPONSE:
            self._handle_awaiting_response_state(event)
        elif self.current_state == State.ALARMING:
            self._handle_alarming_state(event)

    def _handle_disengaged_state(self, event):
        timestamp = event['timestamp']
        if event['type'] == 'driver' and event['event_type'] == 'ENGAGE':
            self._transition_state(State.ENGAGED, timestamp, "Driver engaged system")
            self.last_attentiveness_prompt_time = timestamp

    def _handle_engaged_state(self, event):
        timestamp = event['timestamp']

        # Attentiveness check
        if timestamp - self.last_attentiveness_prompt_time >= 120 * 1000: # 120 seconds in milliseconds
            self.csv_manager.append_commands_log(timestamp, "Steering Motor", "SMALL_MOVEMENT")
            self._transition_state(State.AWAITING_RESPONSE, timestamp, "Attentiveness Prompt")
            self.awaiting_response_start_time = timestamp
            return

        if event['type'] == 'driver' and event['event_type'] == 'DISENGAGE':
            self._transition_state(State.DISENGAGED, timestamp, "Driver disengaged system")
        elif event['type'] == 'sensor' and event['sensor_type'] == 'Camera':
            # Assuming values for lane keeping and cruise control
            lane_keeping_correction = "0.5" # Placeholder
            cruise_control_adjustment = "100" # Placeholder

            self.csv_manager.append_feature_decision(timestamp, "Lane Keeping", lane_keeping_correction)
            self.csv_manager.append_feature_decision(timestamp, "Cruise Control", cruise_control_adjustment)
            self.csv_manager.append_commands_log(timestamp, "Steering Motor", lane_keeping_correction)
            self.csv_manager.append_commands_log(timestamp, "Speed Actuator", cruise_control_adjustment)
            print(f"[{timestamp}] Camera sensor processed: Lane Keeping: {lane_keeping_correction}, Cruise Control: {cruise_control_adjustment}")
        elif event['type'] == 'sensor':
            # Log non-braking decision for other sensor types if not Lidar < 5m
            if event['sensor_type'] == 'Lidar':
                self.csv_manager.append_feature_decision(timestamp, "Emergency Braking", "No Brake")


    def _handle_awaiting_response_state(self, event):
        timestamp = event['timestamp']
        if event['type'] == 'driver' and event['event_type'] == 'STEERING_FORCE':
            force_value = int(event['value'])
            if force_value <= 3:
                self._transition_state(State.ENGAGED, timestamp, "Driver Response Valid")
                self.last_attentiveness_prompt_time = timestamp
                return
            elif 3 < force_value <= 10:
                print(f"[{timestamp}] Driver response ignored (Steering Force: {force_value}N). Still Awaiting Response.")
                return

        # Check for timeout
        if timestamp - self.awaiting_response_start_time >= 5 * 1000: # 5 seconds in milliseconds
            self._transition_state(State.ALARMING, timestamp, "Attentiveness Timeout")
            self.csv_manager.append_commands_log(timestamp, "Alarm Actuator", "CONTINUOUS_ALARM")
            print(f"[{timestamp}] Attentiveness Timeout: Transitioned to ALARMING state.")
            return

    def _handle_alarming_state(self, event):
        timestamp = event['timestamp']
        if event['type'] == 'driver' and event['event_type'] == 'STEERING_FORCE' and int(event['value']) <= 3:
            self._transition_state(State.ENGAGED, timestamp, "Alarm Reset by Driver (Steering Force <= 3N)")
            self.csv_manager.append_commands_log(timestamp, "Alarm Actuator", "STOP_ALARM") # Stop alarm command
            self.last_attentiveness_prompt_time = timestamp
        else:
            # Continue alarming if no valid response to disengage alarm
            self.csv_manager.append_commands_log(timestamp, "Alarm Actuator", "CONTINUOUS_ALARM") # Ensure continuous alarm
            print(f"[{timestamp}] Still in ALARMING state. Alarm continues.")


def main():
    parser = argparse.ArgumentParser(description="Copilot driver-assistance system simulation.")
    parser.add_argument("--input", required=True, help="Path to the input directory containing sensor_log.csv and driver_events.csv.")
    parser.add_argument("--output", required=True, help="Path to the output directory for state_log.csv, commands_log.csv, and feature_decision.csv.")
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    if not os.path.isdir(input_dir):
        print(f"Error: Input directory '{input_dir}' not found.")
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: '{output_dir}'")
    elif not os.path.isdir(output_dir):
        print(f"Error: Output path '{output_dir}' exists but is not a directory.")
        return

    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")

    csv_manager = CSVManager(input_dir, output_dir)
    sensor_events = csv_manager.read_sensor_log()
    driver_events = csv_manager.read_driver_events()

    print(f"Read {len(sensor_events)} sensor events.")
    print(f"Read {len(driver_events)} driver events.")

    # Merge and sort events
    for event in sensor_events:
        event['type'] = 'sensor'
    for event in driver_events:
        event['type'] = 'driver'

    all_events = sorted(sensor_events + driver_events, key=lambda x: x['timestamp'])

    print(f"Total {len(all_events)} events after merging and sorting.")

    copilot = Copilot(csv_manager)

    for event in all_events:
        # Before processing any event, check for AWAITING_RESPONSE timeout
        if copilot.current_state == State.AWAITING_RESPONSE:
            # Check for timeout even if the current event is not a driver event
            if event['timestamp'] - copilot.awaiting_response_start_time >= 5 * 1000: # 5 seconds in milliseconds
                copilot._transition_state(State.ALARMING, event['timestamp'], "Attentiveness Timeout")
                copilot.csv_manager.append_commands_log(event['timestamp'], "Alarm Actuator", "CONTINUOUS_ALARM")
                print(f"[{event['timestamp']}] Attentiveness Timeout: Transitioned to ALARMING state.")
                # If a timeout occurs, the current event is effectively processed in the new state,
                # so we can continue with its normal processing.

        copilot.process_event(event)

    print("\nCopilot simulation finished.")

if __name__ == "__main__":
    main()
