import argparse
import csv
import os
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Union, Deque


# --- Enums ---

class SystemState(Enum):
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"

class SensorType(Enum):
    LIDAR = "LIDAR"
    CAMERA = "CAMERA"

class DriverEventType(Enum):
    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"

# --- Data Models ---

@dataclass
class Event:
    timestamp: int

    def __lt__(self, other):
        return self.timestamp < other.timestamp

@dataclass
class SensorEvent(Event):
    sensor_id: str
    sensor_type: SensorType
    data_value: float
    unit: str

@dataclass
class DriverEvent(Event):
    event_type: DriverEventType
    value: Union[float, str]

@dataclass
class StateLogEntry:
    timestamp: int
    previous_state: SystemState
    current_state: SystemState
    trigger_event: str

@dataclass
class CommandLogEntry:
    timestamp: int
    actuator_id: str
    values: str # Can be single value or comma-separated for multiple (e.g., steering, speed)

@dataclass
class FeatureDecisionEntry:
    timestamp: int
    feature: str
    decision: str

# --- CSV Utilities ---

def read_sensor_log(filepath: str) -> List[SensorEvent]:
    events = []
    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append(
                SensorEvent(
                    timestamp=int(row['timestamp']),
                    sensor_id=row['sensor_id'],
                    sensor_type=SensorType[row['sensor_type'].upper()],
                    data_value=float(row['data_value']),
                    unit=row['unit']
                )
            )
    return events

def read_driver_events(filepath: str) -> List[DriverEvent]:
    events = []
    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            event_type = DriverEventType[row['event_type'].upper()]
            value = float(row['value']) if row['value'].replace('.', '', 1).isdigit() else row['value']
            events.append(
                DriverEvent(
                    timestamp=int(row['timestamp']),
                    event_type=event_type,
                    value=value
                )
            )
    return events

def write_csv(filepath: str, header: List[str], data: List[Union[StateLogEntry, CommandLogEntry, FeatureDecisionEntry]]):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for entry in data:
            writer.writerow(entry.__dict__.values())

# --- Copilot System ---

class Copilot:
    ATTENTIVENESS_PROMPT_INTERVAL = 120 * 1000  # 120 seconds in milliseconds
    ATTENTIVENESS_RESPONSE_WINDOW = 5 * 1000    # 5 seconds in milliseconds
    LIDAR_BRAKING_DISTANCE = 5.0
    DRIVER_ATTENTIVE_FORCE = 3.0
    DRIVER_OVERRIDE_FORCE = 10.0

    def __init__(self, output_dir: str):
        self.state: SystemState = SystemState.DISENGAGED
        self.last_state_transition_time: int = 0 # To track state changes for logging
        self.last_attentiveness_prompt_time: int = 0
        self.attentiveness_prompt_active: bool = False
        self.awaiting_response_start_time: int = 0

        self.state_log: List[StateLogEntry] = []
        self.commands_log: List[CommandLogEntry] = []
        self.feature_decision_log: List[FeatureDecisionEntry] = []

        self.output_dir = output_dir

        # Initialize the state log with the initial state
        self._log_state_transition(0, SystemState.DISENGAGED, "System Start")

    def _log_state_transition(self, timestamp: int, new_state: SystemState, trigger_event: str):
        if self.state != new_state:
            self.state_log.append(
                StateLogEntry(
                    timestamp=timestamp,
                    previous_state=self.state,
                    current_state=new_state,
                    trigger_event=trigger_event
                )
            )
            self.state = new_state
            self.last_state_transition_time = timestamp # Update the last state transition time

    def _issue_command(self, timestamp: int, actuator_id: str, values: Union[float, str]):
        self.commands_log.append(
            CommandLogEntry(
                timestamp=timestamp,
                actuator_id=actuator_id,
                values=str(values)
            )
        )

    def _log_feature_decision(self, timestamp: int, feature: str, decision: str):
        self.feature_decision_log.append(
            FeatureDecisionEntry(
                timestamp=timestamp,
                feature=feature,
                decision=decision
            )
        )

    def _handle_sensor_event(self, event: SensorEvent):
        current_timestamp = event.timestamp
        print(f"[{current_timestamp}] Processing Sensor Event: {event.sensor_type.value} - {event.data_value}{event.unit}")

        # Emergency Braking (FR-02, PF-01) - always active
        if event.sensor_type == SensorType.LIDAR:
            if event.data_value < self.LIDAR_BRAKING_DISTANCE:
                decision = f"Emergency Braking triggered: Obstacle at {event.data_value}{event.unit}"
                self._log_feature_decision(current_timestamp, "Emergency Braking", decision)
                self._issue_command(current_timestamp, "Braking System", "APPLY_MAX_BRAKE")
                print(f"  --> DECISION: {decision}. COMMAND: Braking System - APPLY_MAX_BRAKE")
                return # Emergency braking takes precedence

            else:
                decision = f"No Emergency Braking: Obstacle at {event.data_value}{event.unit}"
                self._log_feature_decision(current_timestamp, "Emergency Braking", decision)
                print(f"  --> DECISION: {decision}")

        # Only proceed with other features if not in Disengaged mode (except emergency braking)
        if self.state == SystemState.DISENGAGED:
            print("  --> System Disengaged. Logging sensor data without further actions.")
            return

        # Attentiveness Monitoring (FR-03) - Check if prompt needed
        if self.state == SystemState.ENGAGED:
            if current_timestamp - self.last_attentiveness_prompt_time >= self.ATTENTIVENESS_PROMPT_INTERVAL:
                print(f"  --> Attentiveness prompt due. Prompting driver.")
                self._issue_command(current_timestamp, "Steering Motor", "SMALL_WHEEL_MOVEMENT")
                self._log_state_transition(current_timestamp, SystemState.AWAITING_RESPONSE, "Attentiveness Prompt")
                self.attentiveness_prompt_active = True
                self.awaiting_response_start_time = current_timestamp

        if self.state == SystemState.AWAITING_RESPONSE:
            if self.attentiveness_prompt_active and 
               current_timestamp - self.awaiting_response_start_time >= self.ATTENTIVENESS_RESPONSE_WINDOW:
                print(f"  --> No valid response within 5 seconds. Transitioning to Alarming state.")
                self._log_state_transition(current_timestamp, SystemState.ALARMING, "Attentiveness Timeout")
                self._issue_command(current_timestamp, "Alarm Actuator", "CONTINUOUS_ALARM")
                self.attentiveness_prompt_active = False

        # Other Autonomous Features (FR-02, PF-01) - only in Engaged
        if self.state == SystemState.ENGAGED:
            if event.sensor_type == SensorType.CAMERA:
                # Placeholder for Lane Keeping and Cruise Control logic
                lane_keeping_correction = round(event.data_value * 0.1, 2) # Example calculation
                cruise_control_adjustment = round(event.data_value * 0.05, 2) # Example calculation

                self._log_feature_decision(current_timestamp, "Lane Keeping", f"Correction: {lane_keeping_correction}")
                self._log_feature_decision(current_timestamp, "Cruise Control", f"Adjustment: {cruise_control_adjustment}")
                self._issue_command(current_timestamp, "Steering Motor", f"STEER_BY_{lane_keeping_correction}")
                self._issue_command(current_timestamp, "Speed Actuator", f"ADJUST_SPEED_BY_{cruise_control_adjustment}")
                print(f"  --> DECISION: Lane Keeping Correction: {lane_keeping_correction}, Cruise Control Adjustment: {cruise_control_adjustment}")
                print(f"  --> COMMANDS: Steering Motor - STEER_BY_{lane_keeping_correction}, Speed Actuator - ADJUST_SPEED_BY_{cruise_control_adjustment}")

    def _handle_driver_event(self, event: DriverEvent):
        current_timestamp = event.timestamp
        print(f"[{current_timestamp}] Processing Driver Event: {event.event_type.value} - {event.value}")

        # Driver Override (FR-04) - highest priority for driver events
        if event.event_type == DriverEventType.STEERING_FORCE and 
           isinstance(event.value, (int, float)) and event.value > self.DRIVER_OVERRIDE_FORCE:
            print(f"  --> Driver Override detected (> {self.DRIVER_OVERRIDE_FORCE}N). Transitioning to Disengaged.")
            self._log_state_transition(current_timestamp, SystemState.DISENGAGED, f"Driver Override ({event.value}N)")
            self.attentiveness_prompt_active = False # Cancel any active prompt
            return # Override takes precedence

        # State Transitions based on Driver Events (FR-01)
        if event.event_type == DriverEventType.ENGAGE:
            if self.state != SystemState.ENGAGED:
                print("  --> Driver ENGAGE event. Transitioning to Engaged state.")
                self._log_state_transition(current_timestamp, SystemState.ENGAGED, "Driver ENGAGE")
                self.last_attentiveness_prompt_time = current_timestamp # Reset timer on engage
            else:
                print("  --> Already in Engaged state. No state change.")
            self.attentiveness_prompt_active = False # Reset on explicit engage/disengage

        elif event.event_type == DriverEventType.DISENGAGE:
            if self.state != SystemState.DISENGAGED:
                print("  --> Driver DISENGAGE event. Transitioning to Disengaged state.")
                self._log_state_transition(current_timestamp, SystemState.DISENGAGED, "Driver DISENGAGE")
            else:
                print("  --> Already in Disengaged state. No state change.")
            self.attentiveness_prompt_active = False

        # Attentiveness Monitoring (FR-03) - Response handling
        elif event.event_type == DriverEventType.STEERING_FORCE and self.state == SystemState.AWAITING_RESPONSE:
            if isinstance(event.value, (int, float)):
                if event.value <= self.DRIVER_ATTENTIVE_FORCE:
                    print(f"  --> Valid driver response ({event.value}N). Transitioning to Engaged state.")
                    self._log_state_transition(current_timestamp, SystemState.ENGAGED, f"Attentiveness Response ({event.value}N)")
                    self.last_attentiveness_prompt_time = current_timestamp # Reset timer
                    self.attentiveness_prompt_active = False
                elif self.DRIVER_ATTENTIVE_FORCE < event.value <= self.DRIVER_OVERRIDE_FORCE:
                    print(f"  --> Driver force ({event.value}N) ignored. Still awaiting response.")
                    # Do nothing, continue awaiting response
            else:
                print(f"  --> Driver event value '{event.value}' is not a valid steering force.")

        # If in Alarming state and driver applies force <= 3N, transition back to Engaged
        if self.state == SystemState.ALARMING and 
           event.event_type == DriverEventType.STEERING_FORCE and 
           isinstance(event.value, (int, float)) and event.value <= self.DRIVER_ATTENTIVE_FORCE:
            print(f"  --> Driver response ({event.value}N) in Alarming state. Transitioning to Engaged.")
            self._log_state_transition(current_timestamp, SystemState.ENGAGED, f"Alarm Cancelled by Driver ({event.value}N)")
            self.last_attentiveness_prompt_time = current_timestamp # Reset timer
            self.attentiveness_prompt_active = False # Ensure prompt is reset

    def process_events(self, all_events: List[Event]):
        for event in all_events:
            print(f"
--- Current State: {self.state.value} @ {event.timestamp} ---")
            
            # Attentiveness timeout check before processing current event if in AWAITING_RESPONSE
            if self.state == SystemState.AWAITING_RESPONSE and 
               event.timestamp - self.awaiting_response_start_time >= self.ATTENTIVENESS_RESPONSE_WINDOW:
                print(f"[{event.timestamp}] Attentiveness Timeout check triggered before event.")
                self._log_state_transition(event.timestamp, SystemState.ALARMING, "Attentiveness Timeout (Pre-Event)")
                self._issue_command(event.timestamp, "Alarm Actuator", "CONTINUOUS_ALARM")
                self.attentiveness_prompt_active = False

            if isinstance(event, SensorEvent):
                self._handle_sensor_event(event)
            elif isinstance(event, DriverEvent):
                self._handle_driver_event(event)
            else:
                print(f"[{event.timestamp}] Unknown event type: {type(event)}")
            
            # Post-event attentiveness timeout check if still AWAITING_RESPONSE
            if self.state == SystemState.AWAITING_RESPONSE and 
               event.timestamp - self.awaiting_response_start_time >= self.ATTENTIVENESS_RESPONSE_WINDOW:
                print(f"[{event.timestamp}] Attentiveness Timeout check triggered after event.")
                self._log_state_transition(event.timestamp, SystemState.ALARMING, "Attentiveness Timeout (Post-Event)")
                self._issue_command(event.timestamp, "Alarm Actuator", "CONTINUOUS_ALARM")
                self.attentiveness_prompt_active = False
            
            # Continuous alarm in Alarming state (FR-03)
            if self.state == SystemState.ALARMING and (event.timestamp - self.last_state_transition_time) % 1000 == 0:
                 # Re-issue alarm command periodically if still alarming and no driver override
                # This ensures "continuous" alarm in the simulation model
                if self.state == SystemState.ALARMING:
                    self._issue_command(event.timestamp, "Alarm Actuator", "CONTINUOUS_ALARM")


    def flush_outputs(self):
        print("
--- Flushing Output Files ---")
        write_csv(
            os.path.join(self.output_dir, "state_log.csv"),
            ["timestamp", "previous_state", "current_state", "trigger_event"],
            self.state_log
        )
        write_csv(
            os.path.join(self.output_dir, "commands_log.csv"),
            ["timestamp", "actuator_id", "values"],
            self.commands_log
        )
        write_csv(
            os.path.join(self.output_dir, "feature_decision.csv"),
            ["timestamp", "feature", "decision"],
            self.feature_decision_log
        )
        print(f"Output files written to {self.output_dir}")

def main():
    parser = argparse.ArgumentParser(description="Copilot Driver-Assistance System Simulation")
    parser.add_argument("--input", type=str, required=True, help="Path to the input directory containing sensor_log.csv and driver_events.csv")
    parser.add_argument("--output", type=str, required=True, help="Path to the output directory for state_log.csv, commands_log.csv, and feature_decision.csv")
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    print(f"Starting Copilot simulation...")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")

    # 1. Read inputs
    try:
        sensor_events = read_sensor_log(os.path.join(input_dir, "sensor_log.csv"))
        driver_events = read_driver_events(os.path.join(input_dir, "driver_events.csv"))
    except FileNotFoundError as e:
        print(f"Error: Input file not found - {e}")
        return
    except Exception as e:
        print(f"Error reading input files: {e}")
        return

    # 2. Merge and sort all events by timestamp
    all_events: List[Event] = sorted(sensor_events + driver_events)

    # 3. Initialize Copilot and process events
    copilot = Copilot(output_dir)
    copilot.process_events(all_events)

    # 4. Flush all collected outputs to CSV files
    copilot.flush_outputs()
    print("Copilot simulation finished.")

if __name__ == "__main__":
    main()
