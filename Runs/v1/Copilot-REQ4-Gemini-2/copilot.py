import argparse
import csv
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Union, Dict
import os

# --- Enums ---
class State(Enum):
    """Represents the operational states of the Copilot system."""
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"

class SensorType(Enum):
    """Represents the types of sensors providing data to Copilot."""
    LIDAR = "Lidar"
    CAMERA = "Camera"

class DriverEventType(Enum):
    """Represents the types of events initiated by the driver."""
    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"

class FeatureDecisionKind(Enum):
    """Represents the categories of autonomous feature decisions."""
    EMERGENCY_BRAKING = "EmergencyBraking"
    LANE_KEEPING = "LaneKeeping"
    CRUISE_CONTROL = "CruiseControl"

class DecisionValue(Enum):
    """Represents the possible outcomes of feature decisions."""
    BRAKE = "BRAKE"
    NO_BRAKE = "NO_BRAKE"
    ADJUST = "ADJUST"

class Actuator(Enum):
    """Represents the types of physical actuators controlled by Copilot."""
    BRAKING_SYSTEM = "BrakingSystem"
    STEERING_MOTOR = "SteeringMotor"
    SPEED_ACTUATOR = "SpeedActuator"
    ALARM_ACTUATOR = "AlarmActuator"

# --- Constants (from Alloy model) ---
LIDAR_DANGER = 5
OVERRIDE_FORCE = 10
VALID_RESPONSE_FORCE = 3
PROMPT_INTERVAL = 120
RESPONSE_WINDOW = 5

# --- Data Classes for Logs and Events ---

@dataclass
class Event:
    """Base class for all events processed by the Copilot system."""
    timestamp: int

    def __lt__(self, other):
        """Enable sorting events by timestamp."""
        return self.timestamp < other.timestamp

@dataclass
class SensorEvent(Event):
    """Represents data received from a sensor."""
    sensor_id: str
    sensor_type: SensorType
    data_value: int
    unit: str

@dataclass
class DriverEvent(Event):
    """Represents an action or input from the driver."""
    event_type: DriverEventType
    value: Union[int, None] = None # For STEERING_FORCE

@dataclass
class StateLogEntry:
    """Records a change in the Copilot's operational state."""
    timestamp: int
    previous_state: State
    current_state: State
    trigger_event: str = "Internal" # Could be event type or "Internal"

@dataclass
class Command:
    """Represents a command issued to a physical actuator."""
    timestamp: int
    actuator_id: str # Should map to Actuator enum, but keeping as string for CSV output
    value: str = "Activate" # Default value for commands

@dataclass
class FeatureDecision:
    """Records a decision made by an autonomous feature."""
    timestamp: int
    feature: FeatureDecisionKind
    decision: DecisionValue

# --- System State ---
class SystemState:
    """Manages the current state and logs of the Copilot system."""
    def __init__(self):
        self.current_state: State = State.DISENGAGED
        self.current_time: int = 0
        self.last_prompt: int = 0
        self.awaiting_since: int = 0

        self.state_log: List[StateLogEntry] = []
        self.commands_log: List[Command] = []
        self.feature_decision_log: List[FeatureDecision] = []
        self.processed_events: List[Event] = []

    def add_state_log(self, timestamp: int, previous: State, current: State, trigger: str = "Internal"):
        """Records a state transition if the state has changed."""
        if previous != current:
            self.state_log.append(StateLogEntry(timestamp, previous, current, trigger))

    def emit_command(self, timestamp: int, actuator: Actuator, value: str = "Activate"):
        """Records a command issued to an actuator."""
        self.commands_log.append(Command(timestamp, actuator.value, value))

    def emit_feature_decision(self, timestamp: int, feature: FeatureDecisionKind, decision: DecisionValue):
        """Records an autonomous feature decision."""
        self.feature_decision_log.append(FeatureDecision(timestamp, feature, decision))

class Copilot:
    """Main class for the Copilot simulation."""
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.system_state = SystemState()
        self.all_events: List[Event] = []

    def _read_sensor_events(self) -> List[SensorEvent]:
        """Reads sensor events from sensor_log.csv."""
        events: List[SensorEvent] = []
        file_path = os.path.join(self.input_dir, "sensor_log.csv")
        try:
            with open(file_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    events.append(
                        SensorEvent(
                            timestamp=int(row['timestamp']),
                            sensor_id=row['sensor_id'],
                            sensor_type=SensorType[row['sensor_type'].upper()],
                            data_value=int(row['data_value']),
                            unit=row['unit']
                        )
                    )
        except FileNotFoundError:
            print(f"Warning: sensor_log.csv not found in {self.input_dir}")
        return events

    def _read_driver_events(self) -> List[DriverEvent]:
        """Reads driver events from driver_events.csv."""
        events: List[DriverEvent] = []
        file_path = os.path.join(self.input_dir, "driver_events.csv")
        try:
            with open(file_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    value = int(row['value']) if row['value'] else None
                    events.append(
                        DriverEvent(
                            timestamp=int(row['timestamp']),
                            event_type=DriverEventType[row['event_type'].upper()],
                            value=value
                        )
                    )
        except FileNotFoundError:
            print(f"Warning: driver_events.csv not found in {self.input_dir}")
        return events

    def _write_state_log(self):
        """Writes the state log to state_log.csv."""
        os.makedirs(self.output_dir, exist_ok=True)
        with open(os.path.join(self.output_dir, "state_log.csv"), mode='w', newline='', encoding='utf-8') as f:
            fieldnames = ["timestamp", "previous_state", "current_state", "trigger_event"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for entry in self.system_state.state_log:
                writer.writerow({
                    "timestamp": entry.timestamp,
                    "previous_state": entry.previous_state.value,
                    "current_state": entry.current_state.value,
                    "trigger_event": entry.trigger_event
                })

    def _write_commands_log(self):
        """Writes the commands log to commands_log.csv."""
        os.makedirs(self.output_dir, exist_ok=True)
        with open(os.path.join(self.output_dir, "commands_log.csv"), mode='w', newline='', encoding='utf-8') as f:
            fieldnames = ["timestamp", "actuator_id", "values"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for cmd in self.system_state.commands_log:
                writer.writerow({
                    "timestamp": cmd.timestamp,
                    "actuator_id": cmd.actuator_id,
                    "values": cmd.value
                })

    def _write_feature_decision_log(self):
        """Writes the feature decision log to feature_decision.csv."""
        os.makedirs(self.output_dir, exist_ok=True)
        with open(os.path.join(self.output_dir, "feature_decision.csv"), mode='w', newline='', encoding='utf-8') as f:
            fieldnames = ["timestamp", "feature", "decision"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for fd in self.system_state.feature_decision_log:
                writer.writerow({
                    "timestamp": fd.timestamp,
                    "feature": fd.feature.value,
                    "decision": fd.decision.value
                })

    def _handle_sensor_event(self, event: SensorEvent):
        """Processes a sensor event."""
        current_state = self.system_state.current_state

        if event.sensor_type == SensorType.LIDAR:
            if event.data_value < LIDAR_DANGER:
                self.system_state.emit_feature_decision(event.timestamp, FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.BRAKE)
                self.system_state.emit_command(event.timestamp, Actuator.BRAKING_SYSTEM)
            else:
                self.system_state.emit_feature_decision(event.timestamp, FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.NO_BRAKE)
        elif event.sensor_type == SensorType.CAMERA and current_state == State.ENGAGED:
            # Only emit decisions/commands if in Engaged state for Camera events
            self.system_state.emit_feature_decision(event.timestamp, FeatureDecisionKind.LANE_KEEPING, DecisionValue.ADJUST)
            self.system_state.emit_feature_decision(event.timestamp, FeatureDecisionKind.CRUISE_CONTROL, DecisionValue.ADJUST)
            self.system_state.emit_command(event.timestamp, Actuator.STEERING_MOTOR)
            self.system_state.emit_command(event.timestamp, Actuator.SPEED_ACTUATOR)

    def _handle_driver_event(self, event: DriverEvent):
        """Processes a driver event."""
        previous_state = self.system_state.current_state
        new_state = previous_state
        trigger_event_str = event.event_type.value

        if event.event_type == DriverEventType.ENGAGE:
            if previous_state == State.DISENGAGED:
                new_state = State.ENGAGED
                self.system_state.last_prompt = event.timestamp # Reset prompt timer
        elif event.event_type == DriverEventType.DISENGAGE:
            if previous_state != State.DISENGAGED:
                new_state = State.DISENGAGED
        elif event.event_type == DriverEventType.STEERING_FORCE:
            force = event.value
            if force is not None:
                if force > OVERRIDE_FORCE: # FR-04: Override always disengages
                    if previous_state != State.DISENGAGED: # Only log state change if actually changing
                        new_state = State.DISENGAGED
                elif previous_state == State.AWAITING_RESPONSE and force <= VALID_RESPONSE_FORCE:
                    new_state = State.ENGAGED
                    self.system_state.last_prompt = event.timestamp # Reset prompt timer
                elif previous_state == State.ALARMING and force <= VALID_RESPONSE_FORCE:
                    new_state = State.ENGAGED
                    self.system_state.last_prompt = event.timestamp # Reset prompt timer
                # Ignored mid-range force while AwaitingResponse -> no-op, keep waiting
                # Other cases (e.g., low force in Disengaged/Engaged) -> no-op

        self.system_state.add_state_log(event.timestamp, previous_state, new_state, trigger_event_str)
        self.system_state.current_state = new_state

    def _write_logs_and_exit(self):
        """Writes all accumulated logs to CSV files and signals simulation completion."""
        print("Simulation finished. Writing output logs...")
        self._write_state_log()
        self._write_commands_log()
        self._write_feature_decision_log()
        print("Output logs written successfully.")

    def run_simulation(self):
        """Runs the Copilot simulation following the Alloy model's discrete time steps."""
        print("Starting Copilot simulation...")
        
        # 1. Read all events and sort them by timestamp
        sensor_events = self._read_sensor_events()
        driver_events = self._read_driver_events()
        self.all_events = sorted(sensor_events + driver_events, key=lambda e: e.timestamp)

        # Initialize current_time. If no events, start at 0. Otherwise, it will advance from 0.
        self.system_state.current_time = 0 
        event_queue_idx = 0
        
        # Determine a simulation safety limit to prevent infinite loops, especially in ALARMING state
        max_possible_event_time = self.all_events[-1].timestamp if self.all_events else 0
        # Allow enough time for all possible internal transitions after the last event
        simulation_safety_limit = max_possible_event_time + PROMPT_INTERVAL + RESPONSE_WINDOW + 20 

        print(f"Initial State: {self.system_state.current_state.value} at Time: {self.system_state.current_time}")

        while True:
            current_time = self.system_state.current_time
            state_before_tick = self.system_state.current_state # Capture state before any changes in this tick
            
            # --- Phase 1: Process external events occurring at current_time ---
            # Process all external events that share the exact current_time timestamp
            while event_queue_idx < len(self.all_events) and self.all_events[event_queue_idx].timestamp == current_time:
                event = self.all_events[event_queue_idx]
                # print(f"DEBUG: [{current_time}] Processing external event: {event}")
                if isinstance(event, SensorEvent):
                    self._handle_sensor_event(event)
                elif isinstance(event, DriverEvent):
                    self._handle_driver_event(event)
                self.system_state.processed_events.append(event)
                event_queue_idx += 1
            
            # --- Phase 2: Process internal transitions/actions at current_time ---
            # These conditions are mutually exclusive in terms of state transitions (as per Alloy's 'one State' assignment for currentState')
            # but can emit commands or logs.
            
            # Capture state before internal step to log transitions correctly
            current_state_for_internal = self.system_state.current_state 
            
            # Condition 1: Engaged -> AwaitingResponse (Prompt Interval)
            if (current_state_for_internal == State.ENGAGED and
                    current_time >= self.system_state.last_prompt + PROMPT_INTERVAL):
                # print(f"DEBUG: [{current_time}] Internal: Prompt interval reached.")
                previous_state_for_log = self.system_state.current_state
                self.system_state.current_state = State.AWAITING_RESPONSE
                self.system_state.awaiting_since = current_time
                self.system_state.emit_command(current_time, Actuator.STEERING_MOTOR, "Prompt")
                self.system_state.add_state_log(current_time, previous_state_for_log, State.AWAITING_RESPONSE, "Internal Prompt")
            
            # Condition 2: AwaitingResponse -> Alarming (Response Window Timeout)
            elif (current_state_for_internal == State.AWAITING_RESPONSE and
                    current_time >= self.system_state.awaiting_since + RESPONSE_WINDOW):
                # print(f"DEBUG: [{current_time}] Internal: Awaiting response timeout.")
                previous_state_for_log = self.system_state.current_state
                self.system_state.current_state = State.ALARMING
                self.system_state.emit_command(current_time, Actuator.ALARM_ACTUATOR)
                self.system_state.add_state_log(current_time, previous_state_for_log, State.ALARMING, "Internal Timeout")
            
            # Condition 3: Alarming state (emit command every tick)
            elif current_state_for_internal == State.ALARMING:
                # print(f"DEBUG: [{current_time}] Internal: Alarming state, emitting alarm command.")
                self.system_state.emit_command(current_time, Actuator.ALARM_ACTUATOR)
                # No state change (Alarming -> Alarming), but a command is emitted, which counts as an action.

            # --- Phase 3: Termination Check ---
            has_pending_external_events = event_queue_idx < len(self.all_events)
            
            # Check if there are any internal conditions that *could* trigger in the future (at current_time + 1 or later)
            # This is complex, but for simplicity, we check if current state implies future actions.
            # If ALARMING, it always acts. If ENGAGED, it might prompt. If AWAITING_RESPONSE, it might timeout.
            is_system_active = (
                has_pending_external_events or
                self.system_state.current_state == State.ALARMING or
                (self.system_state.current_state == State.ENGAGED and 
                 current_time < self.system_state.last_prompt + PROMPT_INTERVAL) or # Prompt not yet due but might become due
                (self.system_state.current_state == State.AWAITING_RESPONSE and 
                 current_time < self.system_state.awaiting_since + RESPONSE_WINDOW) # Timeout not yet due but might become due
            )

            if not is_system_active:
                print(f"[{current_time}] No more external events, and no internal transitions pending. Terminating simulation.")
                break
            
            # Safety break for excessively long simulations
            if current_time > simulation_safety_limit:
                print(f"[{current_time}] Simulation time limit reached ({simulation_safety_limit}). Terminating to prevent infinite loop.")
                break
                
            # --- Phase 4: Advance Time ---
            self.system_state.current_time += 1
            
            # print(f"DEBUG: [{current_time}] -> Next Time: {self.system_state.current_time}, Current State: {self.system_state.current_state.value}")

        self._write_logs_and_exit()

def main():
    parser = argparse.ArgumentParser(description="Copilot: Advanced Driver Assistance System Simulation.")
    parser.add_argument("--input", type=str, required=True, help="Path to the input directory containing sensor_log.csv and driver_events.csv.")
    parser.add_argument("--output", type=str, required=True, help="Path to the output directory where state_log.csv, commands_log.csv, and feature_decision.csv will be written.")
    
    args = parser.parse_args()

    copilot = Copilot(args.input, args.output)
    copilot.run_simulation()

if __name__ == "__main__":
    main()
