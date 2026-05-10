import argparse
import csv
import os
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import time

# --- Enums ---

class CopilotState(Enum):
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"

class SensorType(Enum):
    LIDAR = "Lidar"
    CAMERA = "Camera"

class DriverEventType(Enum):
    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"

class ActuatorID(Enum):
    BRAKING_SYSTEM = "BrakingSystem"
    STEERING_MOTOR = "SteeringMotor"
    SPEED_ACTUATOR = "SpeedActuator"
    ALARM_ACTUATOR = "AlarmActuator"

class FeatureType(Enum):
    EMERGENCY_BRAKING = "EmergencyBraking"
    LANE_KEEPING = "LaneKeeping"
    CRUISE_CONTROL = "CruiseControl"

# --- Data Classes for Events ---

@dataclass
class SensorEvent:
    timestamp: float
    sensor_id: str
    sensor_type: SensorType
    data_value: float
    unit: str
    event_type: str = "sensor"

@dataclass
class DriverEvent:
    timestamp: float
    event_type: DriverEventType
    value: float
    original_type: str = "driver" # To distinguish from merged event_type

@dataclass
class MergedEvent:
    timestamp: float
    event: any # Can be SensorEvent or DriverEvent
    event_type: str # "sensor" or "driver"

# --- Data Classes for Output ---

@dataclass
class StateLogEntry:
    timestamp: float
    previous_state: CopilotState
    current_state: CopilotState
    trigger_event: str

@dataclass
class CommandLogEntry:
    timestamp: float
    actuator_id: ActuatorID
    values: str # Can be float or string, store as string for simplicity

@dataclass
class FeatureDecisionEntry:
    timestamp: float
    feature: FeatureType
    decision: str # Can be float or string, store as string for simplicity

# --- Copilot System ---

class CopilotSystem:
    def __init__(self):
        self.state: CopilotState = CopilotState.DISENGAGED
        self.last_attentiveness_prompt_time: float = 0.0
        self.awaiting_response_start_time: float = 0.0
        self.output_state_log: list[StateLogEntry] = []
        self.output_command_log: list[CommandLogEntry] = []
        self.output_feature_decision: list[FeatureDecisionEntry] = []

    def _log_state_transition(self, timestamp: float, prev_state: CopilotState, current_state: CopilotState, trigger_event: str):
        if prev_state != current_state:
            self.output_state_log.append(StateLogEntry(timestamp, prev_state, current_state, trigger_event))

    def _issue_command(self, timestamp: float, actuator: ActuatorID, value: any):
        self.output_command_log.append(CommandLogEntry(timestamp, actuator, str(value)))

    def _record_feature_decision(self, timestamp: float, feature: FeatureType, decision: any):
        self.output_feature_decision.append(FeatureDecisionEntry(timestamp, feature, str(decision)))

    def process_driver_event(self, event: DriverEvent):
        current_state = self.state
        trigger = f"{event.event_type.value}:{event.value}" if event.event_type == DriverEventType.STEERING_FORCE else event.event_type.value

        # FR-04: Driver Override
        if event.event_type == DriverEventType.STEERING_FORCE and event.value > 10.0:
            if self.state != CopilotState.DISENGAGED:
                self.state = CopilotState.DISENGAGED
                self._log_state_transition(event.timestamp, current_state, self.state, "DRIVER_OVERRIDE")
            print(f"[{event.timestamp:.2f}] Driver override detected. State: {self.state.value}")
            return # Override takes precedence

        # Handle ENGAGE/DISENGAGE
        if event.event_type == DriverEventType.ENGAGE:
            if self.state == CopilotState.DISENGAGED:
                self.state = CopilotState.ENGAGED
                self._log_state_transition(event.timestamp, current_state, self.state, trigger)
                self.last_attentiveness_prompt_time = event.timestamp
                print(f"[{event.timestamp:.2f}] Driver engaged system. State: {self.state.value}")
            return
        elif event.event_type == DriverEventType.DISENGAGE:
            if self.state != CopilotState.DISENGAGED:
                self.state = CopilotState.DISENGAGED
                self._log_state_transition(event.timestamp, current_state, self.state, trigger)
                print(f"[{event.timestamp:.2f}] Driver disengaged system. State: {self.state.value}")
            return
        
        # FR-03: Attentiveness monitoring response
        if self.state == CopilotState.AWAITING_RESPONSE and event.event_type == DriverEventType.STEERING_FORCE:
            if event.value <= 3.0: # Valid response
                self.state = CopilotState.ENGAGED
                self._log_state_transition(event.timestamp, current_state, self.state, trigger)
                self.last_attentiveness_prompt_time = event.timestamp
                print(f"[{event.timestamp:.2f}] Attentiveness confirmed. State: {self.state.value}")
            elif 3.0 < event.value <= 10.0: # Ignored response
                print(f"[{event.timestamp:.2f}] Attentiveness response ignored (force: {event.value}). State: {self.state.value}")
            # If force > 10.0, it's handled by FR-04, which is checked first.

        # FR-03: Escaping Alarming state
        if self.state == CopilotState.ALARMING and event.event_type == DriverEventType.STEERING_FORCE:
            if event.value <= 3.0:
                self.state = CopilotState.ENGAGED
                self._log_state_transition(event.timestamp, current_state, self.state, trigger)
                self.last_attentiveness_prompt_time = event.timestamp
                print(f"[{event.timestamp:.2f}] Driver response in Alarming. State: {self.state.value}")


    def process_sensor_event(self, event: SensorEvent):
        current_state = self.state
        trigger = f"{event.sensor_type.value}:{event.data_value}"

        # PF-01, FR-02: Emergency braking always evaluated first, regardless of mode
        if event.sensor_type == SensorType.LIDAR:
            if event.data_value < 5.0:
                self._record_feature_decision(event.timestamp, FeatureType.EMERGENCY_BRAKING, "BRAKE")
                self._issue_command(event.timestamp, ActuatorID.BRAKING_SYSTEM, "FULL_BRAKE")
                print(f"[{event.timestamp:.2f}] Lidar ( 緊急ブレーキ): Distance {event.data_value:.2f}m. Full Brake issued.")
                return # Abandon other processing for this cycle
            else:
                self._record_feature_decision(event.timestamp, FeatureType.EMERGENCY_BRAKING, "NO_BRAKE")
                print(f"[{event.timestamp:.2f}] Lidar (Emergency Braking): Distance {event.data_value:.2f}m. No brake needed.")

        # FR-02: Further actions only in Engaged mode for non-emergency braking
        if self.state == CopilotState.ENGAGED:
            if event.sensor_type == SensorType.CAMERA:
                # For simplicity, let's assume a dummy calculation for lane keeping and cruise control
                lane_keeping_correction = event.data_value * 0.1 # Example value
                cruise_control_adjustment = event.data_value * 0.05 # Example value

                self._record_feature_decision(event.timestamp, FeatureType.LANE_KEEPING, lane_keeping_correction)
                self._issue_command(event.timestamp, ActuatorID.STEERING_MOTOR, lane_keeping_correction)
                
                self._record_feature_decision(event.timestamp, FeatureType.CRUISE_CONTROL, cruise_control_adjustment)
                self._issue_command(event.timestamp, ActuatorID.SPEED_ACTUATOR, cruise_control_adjustment)
                print(f"[{event.timestamp:.2f}] Camera (Engaged): LaneKeeping {lane_keeping_correction:.2f}, CruiseControl {cruise_control_adjustment:.2f}.")
        elif self.state == CopilotState.DISENGAGED:
            # FR-02: In Disengaged mode, data is logged but no further actions.
            # Lidar emergency braking is already handled above.
            print(f"[{event.timestamp:.2f}] Sensor event ({event.sensor_type.value}) in Disengaged mode. Logging only.")
        
    def _check_attentiveness(self, current_timestamp: float):
        current_state = self.state
        if self.state == CopilotState.ENGAGED:
            if (current_timestamp - self.last_attentiveness_prompt_time) >= 120.0:
                self.state = CopilotState.AWAITING_RESPONSE
                self.awaiting_response_start_time = current_timestamp
                self._log_state_transition(current_timestamp, current_state, self.state, "ATTENTIVENESS_PROMPT")
                self._issue_command(current_timestamp, ActuatorID.STEERING_MOTOR, "SMALL_MOVEMENT")
                print(f"[{current_timestamp:.2f}] Attentiveness prompt issued. State: {self.state.value}")
        elif self.state == CopilotState.AWAITING_RESPONSE:
            if (current_timestamp - self.awaiting_response_start_time) >= 5.0:
                self.state = CopilotState.ALARMING
                self._log_state_transition(current_timestamp, current_state, self.state, "NO_RESPONSE_TIMEOUT")
                self._issue_command(current_timestamp, ActuatorID.ALARM_ACTUATOR, "CONTINUOUS_ALARM")
                print(f"[{current_timestamp:.2f}] No attentiveness response. State: {self.state.value}")
    
    def process_event_stream(self, merged_events: list[MergedEvent]):
        print("Starting event stream processing...")
        for merged_event in merged_events:
            self._check_attentiveness(merged_event.timestamp) # Check attentiveness before processing the current event

            if merged_event.event_type == "driver":
                self.process_driver_event(merged_event.event)
            elif merged_event.event_type == "sensor":
                self.process_sensor_event(merged_event.event)
            else:
                print(f"Unknown event type: {merged_event.event_type}")
        print("Event stream processing finished.")

# --- CSV Helpers ---

def read_sensor_log(file_path: str) -> list[SensorEvent]:
    events = []
    with open(file_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append(SensorEvent(
                timestamp=float(row['timestamp']),
                sensor_id=row['sensor_id'],
                sensor_type=SensorType(row['sensor_type']),
                data_value=float(row['data_value']),
                unit=row['unit']
            ))
    return events

def read_driver_events(file_path: str) -> list[DriverEvent]:
    events = []
    with open(file_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append(DriverEvent(
                timestamp=float(row['timestamp']),
                event_type=DriverEventType(row['event_type']),
                value=float(row['value']) if row['value'] else 0.0 # Handle empty value for ENGAGE/DISENGAGE
            ))
    return events

def merge_and_sort_events(sensor_events: list[SensorEvent], driver_events: list[DriverEvent]) -> list[MergedEvent]:
    merged = []
    for se in sensor_events:
        merged.append(MergedEvent(timestamp=se.timestamp, event=se, event_type="sensor"))
    for de in driver_events:
        merged.append(MergedEvent(timestamp=de.timestamp, event=de, event_type="driver"))
    
    merged.sort(key=lambda x: x.timestamp)
    return merged

def write_state_log(file_path: str, entries: list[StateLogEntry]):
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'previous_state', 'current_state', 'trigger_event'])
        for entry in entries:
            writer.writerow([entry.timestamp, entry.previous_state.value, entry.current_state.value, entry.trigger_event])

def write_command_log(file_path: str, entries: list[CommandLogEntry]):
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'actuator_id', 'values'])
        for entry in entries:
            writer.writerow([entry.timestamp, entry.actuator_id.value, entry.values])

def write_feature_decision(file_path: str, entries: list[FeatureDecisionEntry]):
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'feature', 'decision'])
        for entry in entries:
            writer.writerow([entry.timestamp, entry.feature.value, entry.decision])


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

    sensor_log_path = os.path.join(input_dir, "sensor_log.csv")
    driver_events_path = os.path.join(input_dir, "driver_events.csv")

    if not os.path.exists(sensor_log_path):
        print(f"Error: sensor_log.csv not found in '{input_dir}'")
        return
    if not os.path.exists(driver_events_path):
        print(f"Error: driver_events.csv not found in '{input_dir}'")
        return

    print(f"Reading sensor events from: {sensor_log_path}")
    sensor_events = read_sensor_log(sensor_log_path)
    print(f"Read {len(sensor_events)} sensor events.")

    print(f"Reading driver events from: {driver_events_path}")
    driver_events = read_driver_events(driver_events_path)
    print(f"Read {len(driver_events)} driver events.")

    print("Merging and sorting events...")
    merged_events = merge_and_sort_events(sensor_events, driver_events)
    print(f"Total merged events: {len(merged_events)}")

    copilot_system = CopilotSystem()
    copilot_system.process_event_stream(merged_events)

    print("Writing output files...")
    write_state_log(os.path.join(output_dir, "state_log.csv"), copilot_system.output_state_log)
    write_command_log(os.path.join(output_dir, "commands_log.csv"), copilot_system.output_command_log)
    write_feature_decision(os.path.join(output_dir, "feature_decision.csv"), copilot_system.output_feature_decision)
    print("Output files written successfully.")

if __name__ == "__main__":
    main()
