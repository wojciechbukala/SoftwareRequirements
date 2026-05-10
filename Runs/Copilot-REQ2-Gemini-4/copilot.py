import argparse
import csv
import os
from enum import Enum

# Define system states
class SystemState(Enum):
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"

# Define Sensor Types
class SensorType(Enum):
    LIDAR = "Lidar"
    CAMERA = "Camera"

# Define Driver Event Types
class DriverEventType(Enum):
    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"

class Copilot:
    def __init__(self, input_dir, output_dir):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.current_state = SystemState.DISENGAGED
        self.last_attentiveness_prompt_time = 0.0
        self.awaiting_response_start_time = 0.0
        self.attentiveness_timer_reset = False # Flag to reset the timer

        # Output file paths
        self.state_log_path = os.path.join(output_dir, 'state_log.csv')
        self.commands_log_path = os.path.join(output_dir, 'commands_log.csv')
        self.feature_decision_path = os.path.join(output_dir, 'feature_decision.csv')

        # Initialize output CSV files with headers
        self._initialize_output_csv()

    def _initialize_output_csv(self):
        os.makedirs(self.output_dir, exist_ok=True)

        with open(self.state_log_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'previous_state', 'current_state', 'trigger_event'])

        with open(self.commands_log_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'actuator_id', 'values'])

        with open(self.feature_decision_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'feature', 'decision'])

    def _write_state_log(self, timestamp, previous_state, current_state, trigger_event):
        with open(self.state_log_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, previous_state.value, current_state.value, trigger_event])
        print(f"[{timestamp:.2f}] STATE CHANGE: {previous_state.value} -> {current_state.value} (Trigger: {trigger_event})")

    def _write_commands_log(self, timestamp, actuator_id, values):
        with open(self.commands_log_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, actuator_id, values])
        print(f"[{timestamp:.2f}] COMMAND: {actuator_id} = {values}")

    def _write_feature_decision_log(self, timestamp, feature, decision):
        with open(self.feature_decision_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, feature, decision])
        print(f"[{timestamp:.2f}] FEATURE DECISION: {feature} = {decision}")

    def _read_sensor_log(self):
        sensor_events = []
        filepath = os.path.join(self.input_dir, 'sensor_log.csv')
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sensor_events.append({
                    'timestamp': float(row['timestamp']),
                    'type': 'sensor',
                    'sensor_id': row['sensor_id'],
                    'sensor_type': row['sensor_type'],
                    'data_value': float(row['data_value']),
                    'unit': row['unit']
                })
        return sensor_events

    def _read_driver_events(self):
        driver_events = []
        filepath = os.path.join(self.input_dir, 'driver_events.csv')
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                value = row['value']
                try:
                    value = float(row['value'])
                except ValueError:
                    pass # Keep as string if it's not a float (e.g., ENGAGE, DISENGAGE)

                driver_events.append({
                    'timestamp': float(row['timestamp']),
                    'type': 'driver',
                    'event_type': row['event_type'],
                    'value': value
                })
        return driver_events

    def _merge_and_sort_events(self, sensor_events, driver_events):
        all_events = sensor_events + driver_events
        all_events.sort(key=lambda x: x['timestamp'])
        return all_events

    def _handle_driver_event(self, event):
        timestamp = event['timestamp']
        event_type = DriverEventType(event['event_type']) # Convert string to Enum
        value = event['value']
        
        previous_state = self.current_state

        # FR-04: Driver Override (Steering force > 10N)
        if event_type == DriverEventType.STEERING_FORCE and isinstance(value, float) and value > 10.0:
            if self.current_state != SystemState.DISENGAGED:
                self._write_state_log(timestamp, previous_state, SystemState.DISENGAGED, f"DriverOverride (Force: {value}N)")
                self.current_state = SystemState.DISENGAGED
            return # Override takes precedence

        if event_type == DriverEventType.ENGAGE:
            if self.current_state == SystemState.DISENGAGED:
                self._write_state_log(timestamp, previous_state, SystemState.ENGAGED, event_type.value)
                self.current_state = SystemState.ENGAGED
                self.last_attentiveness_prompt_time = timestamp # Reset timer on engage
                self.attentiveness_timer_reset = True
        elif event_type == DriverEventType.DISENGAGE:
            if self.current_state != SystemState.DISENGAGED:
                self._write_state_log(timestamp, previous_state, SystemState.DISENGAGED, event_type.value)
                self.current_state = SystemState.DISENGAGED
        elif event_type == DriverEventType.STEERING_FORCE:
            if self.current_state == SystemState.AWAITING_RESPONSE:
                # A valid response is 3N or less
                if isinstance(value, float) and value <= 3.0:
                    self._write_state_log(timestamp, previous_state, SystemState.ENGAGED, f"AttentivenessResponse (Force: {value}N)")
                    self.current_state = SystemState.ENGAGED
                    self.last_attentiveness_prompt_time = timestamp # Reset timer
                    self.attentiveness_timer_reset = True
                # FR-03: Steering force > 3N and < 10N shall be ignored
                elif isinstance(value, float) and 3.0 < value <= 10.0:
                    pass # Ignore
            elif self.current_state == SystemState.ALARMING:
                # System escapes Alarming state if 3N or less is received
                if isinstance(value, float) and value <= 3.0:
                    self._write_state_log(timestamp, previous_state, SystemState.ENGAGED, f"AlarmAcknowledged (Force: {value}N)")
                    self.current_state = SystemState.ENGAGED
                    self.last_attentiveness_prompt_time = timestamp # Reset timer
                    self.attentiveness_timer_reset = True


    def _handle_sensor_event(self, event):
        timestamp = event['timestamp']
        sensor_type = SensorType(event['sensor_type']) # Convert string to Enum
        data_value = event['data_value']

        # PF-01: Every sensor event is first recorded as received.
        # This is implicitly handled by the event processing loop, but we can print for clarity.
        print(f"[{timestamp:.2f}] SENSOR EVENT: {sensor_type.value} - Value: {data_value} {event['unit']}")

        # Emergency Braking - FR-02, PF-01
        if sensor_type == SensorType.LIDAR:
            if data_value < 5.0:
                # Decide on emergency braking
                self._write_feature_decision_log(timestamp, "EmergencyBraking", "TRIGGERED")
                # Issue braking command
                self._write_commands_log(timestamp, "BrakingSystem", "BRAKE")
                # Abandon other features for this cycle
                return
            else:
                self._write_feature_decision_log(timestamp, "EmergencyBraking", "NOT_TRIGGERED")

        # Other sensor events only take action when in Engaged mode - FR-02, PF-01
        if self.current_state == SystemState.ENGAGED:
            if sensor_type == SensorType.CAMERA:
                # Compute Lane Keeping and Cruise Control
                # For simulation, we'll just use dummy values or the data_value itself
                lane_keeping_correction = data_value * 0.1 # Example calculation
                cruise_control_adjustment = data_value * 0.5 # Example calculation

                self._write_feature_decision_log(timestamp, "LaneKeeping", lane_keeping_correction)
                self._write_feature_decision_log(timestamp, "CruiseControl", cruise_control_adjustment)

                self._write_commands_log(timestamp, "SteeringMotor", lane_keeping_correction)
                self._write_commands_log(timestamp, "SpeedActuator", cruise_control_adjustment)
        elif self.current_state == SystemState.DISENGAGED:
            print(f"[{timestamp:.2f}] System Disengaged. Logging sensor data without further actions.")

    def run_simulation(self):
        sensor_events = self._read_sensor_log()
        driver_events = self._read_driver_events()
        all_events = self._merge_and_sort_events(sensor_events, driver_events)

        print("Starting Copilot simulation...")
        print(f"Initial State: {self.current_state.value}")
        
        # FR-03: Attentiveness monitoring - check every 120 seconds
        # We need to handle this proactively between events or on a timer.
        # The timestamp of the events can serve as our timeline.

        for event in all_events:
            timestamp = event['timestamp']

            # Attentiveness check logic (FR-03)
            # This needs to be checked before processing the current event,
            # to ensure prompts are issued at the correct times,
            # and state transitions (AwaitingResponse, Alarming) occur.

            # Handle AWAITING_RESPONSE timeout
            if self.current_state == SystemState.AWAITING_RESPONSE:
                if timestamp - self.awaiting_response_start_time >= 5.0:
                    previous_state = self.current_state
                    self._write_state_log(timestamp, previous_state, SystemState.ALARMING, "AttentivenessTimeout")
                    self.current_state = SystemState.ALARMING
                    self._write_commands_log(timestamp, "AlarmActuator", "ON") # Emit continuous alarm

            # Check if it's time for an attentiveness prompt
            if self.current_state == SystemState.ENGAGED:
                if timestamp - self.last_attentiveness_prompt_time >= 120.0:
                    previous_state = self.current_state
                    self._write_state_log(timestamp, previous_state, SystemState.AWAITING_RESPONSE, "AttentivenessPrompt")
                    self.current_state = SystemState.AWAITING_RESPONSE
                    self._write_commands_log(timestamp, "SteeringWheel", "PROMPT") # Small steering wheel movement
                    self.awaiting_response_start_time = timestamp # Start waiting timer
                    self.last_attentiveness_prompt_time = timestamp # Reset prompt timer

            # Reset attentiveness timer only if a valid response was registered
            if self.attentiveness_timer_reset and self.current_state == SystemState.ENGAGED:
                self.last_attentiveness_prompt_time = timestamp
                self.attentiveness_timer_reset = False


            if event['type'] == 'sensor':
                self._handle_sensor_event(event)
            elif event['type'] == 'driver':
                self._handle_driver_event(event)

        print("Copilot simulation finished.")

def main():
    parser = argparse.ArgumentParser(description="Copilot driver-assistance system simulation.")
    parser.add_argument("--input", type=str, required=True, help="Path to the input directory containing sensor_log.csv and driver_events.csv.")
    parser.add_argument("--output", type=str, required=True, help="Path to the output directory for state_log.csv, commands_log.csv, and feature_decision.csv.")
    
    args = parser.parse_args()

    copilot = Copilot(args.input, args.output)
    copilot.run_simulation()

if __name__ == "__main__":
    main()
