import argparse
import csv
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Union

# --- Enums ---
class State(Enum):
    """Represents the possible states of the Copilot system."""
    Disengaged = auto()
    Engaged = auto()
    AwaitingResponse = auto()
    Alarming = auto()

class SensorType(Enum):
    """Represents the types of sensors."""
    Lidar = auto()
    Camera = auto()

class DriverEventType(Enum):
    """Represents the types of driver events."""
    ENGAGE = auto()
    DISENGAGE = auto()
    STEERING_FORCE = auto()

class FeatureDecisionKind(Enum):
    """Represents the kinds of feature decisions made by the system."""
    EmergencyBraking = auto()
    LaneKeeping = auto()
    CruiseControl = auto()

class DecisionValue(Enum):
    """Represents the possible values for feature decisions."""
    BRAKE = auto()
    NO_BRAKE = auto()
    ADJUST = auto()

class Actuator(Enum):
    """Represents the types of actuators."""
    BrakingSystem = auto()
    SteeringMotor = auto()
    SpeedActuator = auto()
    AlarmActuator = auto()

# --- Threshold Constants ---
LIDAR_DANGER = 5
OVERRIDE_FORCE = 10
VALID_RESPONSE_FORCE = 3
PROMPT_INTERVAL = 120  # In seconds for simulation
RESPONSE_WINDOW = 5    # In seconds for simulation

# --- Data Classes for Logs and Events ---

@dataclass
class StateLogEntry:
    """Represents an entry in the state change log."""
    time: float
    previous: State
    current: State
    trigger_event: str # For output, storing event type or internal trigger

@dataclass
class Command:
    """Represents a command issued to an actuator."""
    time: float
    target: Actuator
    value: Union[str, float] = "" # For cases where a command has a value (e.g., speed)

@dataclass
class FeatureDecision:
    """Represents a decision made by a feature."""
    time: float
    feature: FeatureDecisionKind
    decision: Union[str, float]

@dataclass
class Event:
    """Base class for all events."""
    time: float

    def __lt__(self, other):
        """Enable sorting events by time."""
        return self.time < other.time

@dataclass
class SensorEvent(Event):
    """Represents a sensor data event."""
    sensor_id: str
    sensor_type: SensorType
    data_value: float
    unit: str = ""

@dataclass
class DriverEvent(Event):
    """Represents a driver-initiated event."""
    event_type: DriverEventType
    value: float = None # Force for STEERING_FORCE, or None

# --- System State ---
class SystemState:
    """Manages the current state and logs of the Copilot system."""
    def __init__(self):
        self.current_state: State = State.Disengaged
        self.current_time: float = 0.0
        self.last_prompt: float = 0.0
        self.awaiting_since: float = 0.0
        self.state_log: List[StateLogEntry] = []
        self.commands_log: List[Command] = []
        self.feature_decision_log: List[FeatureDecision] = []
        self.processed_events: List[Event] = []
        self.event_queue: List[Event] = [] # All events to be processed

    def _add_state_log(self, time: float, previous: State, current: State, trigger: str = ""):
        """Appends a state change entry to the state log."""
        if previous != current:
            self.state_log.append(StateLogEntry(time, previous, current, trigger))

    def _emit_command(self, time: float, target: Actuator, value: Union[str, float] = ""):
        """Appends a command entry to the commands log."""
        self.commands_log.append(Command(time, target, value))

    def _emit_feature_decision(self, time: float, feature: FeatureDecisionKind, decision: Union[str, float]):
        """Appends a feature decision entry to the feature decision log."""
        self.feature_decision_log.append(FeatureDecision(time, feature, decision))

    def _tick_time(self, new_time: float):
        """Advances the system's current time."""
        self.current_time = new_time
    
    def get_next_event(self) -> Union[Event, None]:
        """Returns the next event to process from the queue, or None if empty."""
        if self.event_queue:
            return self.event_queue[0]
        return None
    
    def pop_next_event(self) -> Union[Event, None]:
        """Removes and returns the next event from the queue."""
        if self.event_queue:
            event = self.event_queue.pop(0)
            self.processed_events.append(event)
            return event
        return None
    
    def has_pending_events(self) -> bool:
        """Checks if there are any events remaining in the queue."""
        return len(self.event_queue) > 0

    def handle_engage_driver_event(self, event: DriverEvent):
        """Handles an ENGAGE driver event."""
        # Pre-condition: event is already popped from queue, current_time is updated
        previous_state = self.current_state
        if self.current_state == State.Disengaged:
            self.current_state = State.Engaged
            self.last_prompt = self.current_time
            self._add_state_log(event.time, previous_state, self.current_state, event.event_type.name)
        # else: no-op for already engaged states

    def handle_disengage_driver_event(self, event: DriverEvent):
        """Handles a DISENGAGE driver event."""
        previous_state = self.current_state
        if self.current_state != State.Disengaged:
            self.current_state = State.Disengaged
            self._add_state_log(event.time, previous_state, self.current_state, event.event_type.name)
        # else: no-op for already disengaged state

    def handle_steering_force_driver_event(self, event: DriverEvent):
        """Handles a STEERING_FORCE driver event."""
        force = event.value
        previous_state = self.current_state
        
        # Override: force > OVERRIDE_FORCE (10N), any state -> Disengaged (FR-04)
        if force is not None and force > OVERRIDE_FORCE:
            if self.current_state != State.Disengaged:
                self.current_state = State.Disengaged
                self._add_state_log(event.time, previous_state, self.current_state, event.event_type.name)
        # Valid response while AwaitingResponse -> Engaged, reset prompt timer
        elif force is not None and force <= VALID_RESPONSE_FORCE and self.current_state == State.AwaitingResponse:
            self.current_state = State.Engaged
            self.last_prompt = self.current_time
            self.awaiting_since = 0.0 # Reset awaiting_since
            self._add_state_log(event.time, previous_state, self.current_state, event.event_type.name)
        # Alarm escape: low force while Alarming -> Engaged, reset prompt timer
        elif force is not None and force <= VALID_RESPONSE_FORCE and self.current_state == State.Alarming:
            self.current_state = State.Engaged
            self.last_prompt = self.current_time
            self.awaiting_since = 0.0 # Reset awaiting_since
            self._add_state_log(event.time, previous_state, self.current_state, event.event_type.name)
        # Ignored mid-range force while AwaitingResponse -> no-op, keep waiting
        # (f > VALID_RESPONSE_FORCE and f <= OVERRIDE_FORCE and cs = AwaitingResponse) implies no-op
        # Other cases: no-op

    def handle_lidar_sensor_event(self, event: SensorEvent):
        """Handles a Lidar sensor event."""
        # Current state and logs are preserved unless brake command is issued
        
        if event.data_value < LIDAR_DANGER:
            self._emit_feature_decision(event.time, FeatureDecisionKind.EmergencyBraking, DecisionValue.BRAKE.name)
            self._emit_command(event.time, Actuator.BrakingSystem)
        else:
            self._emit_feature_decision(event.time, FeatureDecisionKind.EmergencyBraking, DecisionValue.NO_BRAKE.name)
            
    def handle_camera_sensor_event(self, event: SensorEvent):
        """Handles a Camera sensor event."""
        if self.current_state == State.Engaged:
            # Emit two feature decisions (LaneKeeping + CruiseControl)
            self._emit_feature_decision(event.time, FeatureDecisionKind.LaneKeeping, DecisionValue.ADJUST.name)
            self._emit_feature_decision(event.time, FeatureDecisionKind.CruiseControl, DecisionValue.ADJUST.name)
            # Emit two commands (SteeringMotor + SpeedActuator)
            self._emit_command(event.time, Actuator.SteeringMotor)
            self._emit_command(event.time, Actuator.SpeedActuator)

    def internal_step(self):
        """Performs internal state transitions based on time, independent of external events."""
        previous_state = self.current_state

        # Prompt: Engaged long enough since last prompt -> AwaitingResponse
        if (self.current_state == State.Engaged and
                self.current_time >= self.last_prompt + PROMPT_INTERVAL):
            self.current_state = State.AwaitingResponse
            self.awaiting_since = self.current_time
            self._add_state_log(self.current_time, previous_state, self.current_state, "AttentivenessCheck")
            self._emit_command(self.current_time, Actuator.SteeringMotor, "PromptDriver")

        # Response timeout: AwaitingResponse longer than window -> Alarming
        elif (self.current_state == State.AwaitingResponse and
              self.current_time >= self.awaiting_since + RESPONSE_WINDOW):
            self.current_state = State.Alarming
            self._add_state_log(self.current_time, previous_state, self.current_state, "ResponseTimeout")
            self._emit_command(self.current_time, Actuator.AlarmActuator)
        
        # Alarm tick: keep Alarming, emit one alarm command per tick
        elif self.current_state == State.Alarming:
            self._emit_command(self.current_time, Actuator.AlarmActuator)

    def process_event(self, event: Event):
        """Dispatches an event to the appropriate handler."""
        # This function should only be called if event.time is equal to system.current_time
        # The time has already been advanced by the simulation loop.
        
        if isinstance(event, SensorEvent):
            if event.sensor_type == SensorType.Lidar:
                self.handle_lidar_sensor_event(event)
            elif event.sensor_type == SensorType.Camera:
                self.handle_camera_sensor_event(event)
        elif isinstance(event, DriverEvent):
            if event.event_type == DriverEventType.ENGAGE:
                self.handle_engage_driver_event(event)
            elif event.event_type == DriverEventType.DISENGAGE:
                self.handle_disengage_driver_event(event)
            elif event.event_type == DriverEventType.STEERING_FORCE:
                self.handle_steering_force_driver_event(event)
        
        # The internal_step function is called by the main simulation loop
        # separately, after event processing at the same timestamp if applicable.
        # This prevents double-processing or incorrect ordering.


def read_sensor_log(file_path: str) -> List[SensorEvent]:
    """Reads sensor data from a CSV file."""
    events = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append(SensorEvent(
                time=float(row['timestamp']),
                sensor_id=row['sensor_id'],
                sensor_type=SensorType[row['sensor_type']],
                data_value=float(row['data_value']),
                unit=row['unit']
            ))
    return events

def read_driver_events(file_path: str) -> List[DriverEvent]:
    """Reads driver events from a CSV file."""
    events = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            value = float(row['value']) if row['value'] else None
            events.append(DriverEvent(
                time=float(row['timestamp']),
                event_type=DriverEventType[row['event_type']],
                value=value
            ))
    return events

def write_state_log(file_path: str, log: List[StateLogEntry]):
    """Writes the state log to a CSV file."""
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'previous_state', 'current_state', 'trigger_event'])
        for entry in log:
            writer.writerow([entry.time, entry.previous.name, entry.current.name, entry.trigger_event])

def write_commands_log(file_path: str, log: List[Command]):
    """Writes the commands log to a CSV file."""
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'actuator_id', 'values'])
        for entry in log:
            writer.writerow([entry.time, entry.target.name, entry.value])

def write_feature_decision_log(file_path: str, log: List[FeatureDecision]):
    """Writes the feature decision log to a CSV file."""
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'feature', 'decision'])
        for entry in log:
            writer.writerow([entry.time, entry.feature.name, entry.decision])

def simulate(input_dir: str, output_dir: str):
    """
    Runs the Copilot simulation.
    Reads input events, processes them, and writes output logs.
    """
    system = SystemState()

    # Read all events with robust error handling for missing files
    sensor_events = []
    driver_events = []

    try:
        sensor_events = read_sensor_log(f"{input_dir}/sensor_log.csv")
    except FileNotFoundError:
        print(f"Warning: sensor_log.csv not found in {input_dir}. Continuing without sensor events.")
    except Exception as e:
        print(f"Error reading sensor_log.csv: {e}")

    try:
        driver_events = read_driver_events(f"{input_dir}/driver_events.csv")
    except FileNotFoundError:
        print(f"Warning: driver_events.csv not found in {input_dir}. Continuing without driver events.")
    except Exception as e:
        print(f"Error reading driver_events.csv: {e}")

    # Combine and sort all events by time
    all_events: List[Event] = sorted(sensor_events + driver_events)
    system.event_queue = all_events

    print("Starting Copilot simulation...")
    
    # Main simulation loop, strictly following the Alloy `anyStep` logic
    # `anyStep` is `(some e: Event | step[e]) or internalStep`
    # This means if an external event is scheduled at the current time, it is processed.
    # Otherwise, an internal step is processed (if any conditions are met).
    while True:
        next_event = system.get_next_event()
        
        # Determine the time of the next external event
        next_event_time = float('inf')
        if next_event:
            next_event_time = next_event.time
        
        # Determine the earliest time for an internal step to trigger
        next_internal_trigger_time = float('inf')

        # Check for Engaged -> AwaitingResponse transition (Attentiveness Check)
        if system.current_state == State.Engaged:
            # The earliest time this could happen
            potential_prompt_time = system.last_prompt + PROMPT_INTERVAL
            if potential_prompt_time > system.current_time:
                next_internal_trigger_time = min(next_internal_trigger_time, potential_prompt_time)
            # If current_time has already passed potential_prompt_time, it should trigger at current_time
            elif system.current_time >= potential_prompt_time:
                 next_internal_trigger_time = min(next_internal_trigger_time, system.current_time)


        # Check for AwaitingResponse -> Alarming transition (Response Timeout)
        if system.current_state == State.AwaitingResponse and system.awaiting_since != 0.0:
            # The earliest time this could happen
            potential_timeout_time = system.awaiting_since + RESPONSE_WINDOW
            if potential_timeout_time > system.current_time:
                next_internal_trigger_time = min(next_internal_trigger_time, potential_timeout_time)
            # If current_time has already passed potential_timeout_time, it should trigger at current_time
            elif system.current_time >= potential_timeout_time:
                next_internal_trigger_time = min(next_internal_trigger_time, system.current_time)


        # If in Alarming state, it needs to emit commands continuously, effectively triggering an internal step
        # on every time unit where no external event overrides it.
        # This implies if nothing else is happening, the system.current_time should advance by 1 for alarming.
        if system.current_state == State.Alarming:
             # If next external event is far in the future, then alarm should tick at current_time + 1
             if next_event_time > system.current_time + 1:
                 next_internal_trigger_time = min(next_internal_trigger_time, system.current_time + 1)
             elif next_event_time == float('inf'): # If no events left, keep alarming
                 next_internal_trigger_time = min(next_internal_trigger_time, system.current_time + 1)
             # If an event is at or before current time, and no other internal trigger is set,
             # but we are alarming, ensure an internal step is considered. This handles
             # cases where a fast-forward might skip over a tick for alarming.
             elif next_event_time > system.current_time and next_internal_trigger_time == float('inf'): # event is in future, no other internal trigger
                 next_internal_trigger_time = min(next_internal_trigger_time, system.current_time + 1)
             elif next_event_time <= system.current_time and next_internal_trigger_time == float('inf'): # event at or past, no other internal trigger
                 next_internal_trigger_time = min(next_internal_trigger_time, system.current_time)


        # Determine the effective next simulation time
        effective_next_time = min(next_event_time, next_internal_trigger_time)

        if effective_next_time == float('inf'):
            print(f"[{system.current_time:.1f}] No more events or internal triggers. Simulation stopping.")
            break # No more events or internal triggers, and not in an active alarming state

        # If effective_next_time is the same as current_time, it means an event or internal trigger
        # is due at the current timestamp. We process it.
        # If effective_next_time is greater, it means we need to fast-forward time.
        if effective_next_time > system.current_time:
            # Advance current simulation time to the next significant point
            system._tick_time(effective_next_time)

        # Process external event first if it's due at current_time (priority over internal step)
        if next_event and system.current_time == next_event.time:
            event_to_process = system.pop_next_event()
            print(f"[{system.current_time:.1f}] Event: {event_to_process.__class__.__name__} (type={getattr(event_to_process, 'event_type', getattr(event_to_process, 'sensor_type', 'N/A')).name})")
            
            # Dispatch to appropriate handler
            if isinstance(event_to_process, SensorEvent):
                if event_to_process.sensor_type == SensorType.Lidar:
                    system.handle_lidar_sensor_event(event_to_process)
                elif event_to_process.sensor_type == SensorType.Camera:
                    system.handle_camera_sensor_event(event_to_process)
            elif isinstance(event_to_process, DriverEvent):
                if event_to_process.event_type == DriverEventType.ENGAGE:
                    system.handle_engage_driver_event(event_to_process)
                elif event_to_process.event_type == DriverEventType.DISENGAGE:
                    system.handle_disengage_driver_event(event_to_process)
                elif event_to_process.event_type == DriverEventType.STEERING_FORCE:
                    system.handle_steering_force_driver_event(event_to_process)
        
        # Else, if no external event was processed at this current_time, or if current_time
        # is the result of fast-forwarding to an internal trigger, process internal step.
        # Ensure that internal_step is only processed if it's actually due at current_time
        # (and possibly, no external event took precedence at this exact tick,
        # or it's the continuous alarming).
        else: # No external event at this exact time, check for internal step
             if (system.current_state == State.Engaged and system.current_time >= system.last_prompt + PROMPT_INTERVAL) or 
                (system.current_state == State.AwaitingResponse and system.current_time >= system.awaiting_since + RESPONSE_WINDOW) or 
                (system.current_state == State.Alarming and system.current_time == next_internal_trigger_time):
                 
                 print(f"[{system.current_time:.1f}] Internal Step (State: {system.current_state.name}).")
                 system.internal_step()
                 
        # Output current state for tracing
        print(f"Current State: {system.current_state.name}, Time: {system.current_time:.1f}")

    print("Simulation finished.")

    # Write output logs
    write_state_log(f"{output_dir}/state_log.csv", system.state_log)
    write_commands_log(f"{output_dir}/commands_log.csv", system.commands_log)
    write_feature_decision_log(f"{output_dir}/feature_decision.csv", system.feature_decision_log)


def main():
    parser = argparse.ArgumentParser(description="Copilot: Advanced Driver Assistance System Simulation.")
    parser.add_argument('--input', type=str, required=True, help="Path to the input directory containing sensor_log.csv and driver_events.csv.")
    parser.add_argument('--output', type=str, required=True, help="Path to the output directory for state_log.csv, commands_log.csv, and feature_decision.csv.")
    
    args = parser.parse_args()

    # Ensure output directory exists (basic error handling)
    import os
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    simulate(args.input, args.output)

if __name__ == "__main__":
    main()
