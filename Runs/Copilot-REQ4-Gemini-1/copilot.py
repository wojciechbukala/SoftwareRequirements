#!/usr/bin/env python3
import argparse
import csv
from enum import Enum, auto
from collections import deque

# --- Constants from Alloy model ---
LIDAR_DANGER = 5.0  # float for consistency with other time/data values
OVERRIDE_FORCE = 10.0
VALID_RESPONSE_FORCE = 3.0
PROMPT_INTERVAL = 120.0  # seconds
RESPONSE_WINDOW = 5.0  # seconds

# --- Enumerated domains ---
class State(Enum):
    DISENGAGED = auto()
    ENGAGED = auto()
    AWAITING_RESPONSE = auto()
    ALARMING = auto()

class SensorType(Enum):
    LIDAR = auto()
    CAMERA = auto()

class DriverEventType(Enum):
    ENGAGE = auto()
    DISENGAGE = auto()
    STEERING_FORCE = auto()

class FeatureDecisionKind(Enum):
    EMERGENCY_BRAKING = auto()
    LANE_KEEPING = auto()
    CRUISE_CONTROL = auto()

class DecisionValue(Enum):
    BRAKE = auto()
    NO_BRAKE = auto()
    ADJUST = auto()

class Actuator(Enum):
    BRAKING_SYSTEM = auto()
    STEERING_MOTOR = auto()
    SPEED_ACTUATOR = auto()
    ALARM_ACTUATOR = auto()

# --- Data Structures (equivalent to Alloy signatures) ---

class Event:
    def __init__(self, timestamp: float):
        self.timestamp = timestamp

    def __lt__(self, other):
        return self.timestamp < other.timestamp

class SensorEvent(Event):
    def __init__(self, timestamp: float, sensor_type: SensorType, data_value: float):
        super().__init__(timestamp)
        self.sensor_type = sensor_type
        self.data_value = data_value

class DriverEvent(Event):
    def __init__(self, timestamp: float, event_type: DriverEventType, force: float = None):
        super().__init__(timestamp)
        self.event_type = event_type
        self.force = force

class StateLogEntry:
    def __init__(self, timestamp: float, previous: State, current: State, trigger_event: str):
        self.timestamp = timestamp
        self.previous = previous
        self.current = current
        self.trigger_event = trigger_event

class Command:
    def __init__(self, timestamp: float, target: Actuator, value: str = None):
        self.timestamp = timestamp
        self.target = target
        self.value = value # Used for actuators that might have values (e.g., speed for SpeedActuator)

class FeatureDecision:
    def __init__(self, timestamp: float, feature: FeatureDecisionKind, value: DecisionValue):
        self.timestamp = timestamp
        self.feature = feature
        self.value = value

class SystemState:
    def __init__(self):
        self.current_state = State.DISENGAGED
        self.current_time = 0.0
        self.last_prompt = 0.0
        self.awaiting_since = 0.0

        self.state_log = []
        self.commands_log = []
        self.feature_decision_log = []
        self.processed_events = set() # Not strictly needed for Python execution, but mirrors Alloy

    def add_state_log(self, timestamp: float, previous: State, current: State, trigger_event: str):
        self.state_log.append(StateLogEntry(timestamp, previous, current, trigger_event))

    def emit_command(self, timestamp: float, target: Actuator, value: str = None):
        self.commands_log.append(Command(timestamp, target, value))

    def emit_feature_decision(self, timestamp: float, feature: FeatureDecisionKind, value: DecisionValue):
        self.feature_decision_log.append(FeatureDecision(timestamp, feature, value))

# --- CSV Handling ---

def read_sensor_log(filepath: str) -> list[SensorEvent]:
    events = []
    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                timestamp = float(row['timestamp'])
                sensor_type = SensorType[row['sensor_type'].upper()]
                data_value = float(row['data_value'])
                events.append(SensorEvent(timestamp, sensor_type, data_value))
            except (ValueError, KeyError) as e:
                print(f"Skipping malformed sensor log row: {row} - {e}")
    return events

def read_driver_events(filepath: str) -> list[DriverEvent]:
    events = []
    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                timestamp = float(row['timestamp'])
                event_type = DriverEventType[row['event_type'].upper()]
                force = float(row['value']) if row['value'] else None
                events.append(DriverEvent(timestamp, event_type, force))
            except (ValueError, KeyError) as e:
                print(f"Skipping malformed driver event row: {row} - {e}")
    return events

def write_state_log(filepath: str, log_entries: list[StateLogEntry]):
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'previous_state', 'current_state', 'trigger_event'])
        for entry in log_entries:
            writer.writerow([
                entry.timestamp,
                entry.previous.name,
                entry.current.name,
                entry.trigger_event
            ])

def write_commands_log(filepath: str, log_entries: list[Command]):
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'actuator_id', 'values'])
        for entry in log_entries:
            writer.writerow([
                entry.timestamp,
                entry.target.name,
                entry.value if entry.value is not None else "" # Handle optional value
            ])

def write_feature_decision_log(filepath: str, log_entries: list[FeatureDecision]):
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'feature', 'decision'])
        for entry in log_entries:
            writer.writerow([
                entry.timestamp,
                entry.feature.name,
                entry.value.name
            ])

# --- Event Handlers (Pythonic translation of Alloy predicates) ---

def handle_engage_driver_event(system: SystemState, event: DriverEvent):
    # system.current_time is managed by run_simulation.
    if system.current_state == State.DISENGAGED:
        prev_state = system.current_state
        system.current_state = State.ENGAGED
        system.last_prompt = system.current_time
        system.add_state_log(event.timestamp, prev_state, system.current_state, event.event_type.name)
        print(f"[{system.current_time:.3f}] Driver ENGAGE: System state changed from {prev_state.name} to {system.current_state.name}")
    else:
        print(f"[{system.current_time:.3f}] Driver ENGAGE: No state change from {system.current_state.name}")

def handle_disengage_driver_event(system: SystemState, event: DriverEvent):
    # system.current_time is managed by run_simulation.
    if system.current_state != State.DISENGAGED:
        prev_state = system.current_state
        system.current_state = State.DISENGAGED
        system.add_state_log(event.timestamp, prev_state, system.current_state, event.event_type.name)
        print(f"[{system.current_time:.3f}] Driver DISENGAGE: System state changed from {prev_state.name} to {system.current_state.name}")
    else:
        print(f"[{system.current_time:.3f}] Driver DISENGAGE: No state change from {system.current_state.name}")

def handle_steering_force_driver_event(system: SystemState, event: DriverEvent):
    # system.current_time is managed by run_simulation.
    force = event.force
    prev_state = system.current_state

    if force is None:
        print(f"[{system.current_time:.3f}] Driver STEERING_FORCE without force value. No-op.")
        return

    if force > OVERRIDE_FORCE:
        # Override: force > 10N, any state -> Disengaged (FR-04)
        if system.current_state != State.DISENGAGED:
            system.current_state = State.DISENGAGED
            system.add_state_log(event.timestamp, prev_state, system.current_state, event.event_type.name)
            print(f"[{system.current_time:.3f}] Driver STEERING_FORCE ({force:.1f}N) > OVERRIDE_FORCE. System state changed from {prev_state.name} to {system.current_state.name}")
        else:
            print(f"[{system.current_time:.3f}] Driver STEERING_FORCE ({force:.1f}N) > OVERRIDE_FORCE. Already {system.current_state.name}, no state change.")
    elif force <= VALID_RESPONSE_FORCE:
        if system.current_state == State.AWAITING_RESPONSE:
            # Valid response while AwaitingResponse -> Engaged, reset prompt timer
            system.current_state = State.ENGAGED
            system.last_prompt = system.current_time
            system.add_state_log(event.timestamp, prev_state, system.current_state, event.event_type.name)
            print(f"[{system.current_time:.3f}] Driver STEERING_FORCE ({force:.1f}N) < VALID_RESPONSE_FORCE. Valid response. State changed from {prev_state.name} to {system.current_state.name}")
        elif system.current_state == State.ALARMING:
            # Alarm escape: low force while Alarming -> Engaged, reset prompt timer
            system.current_state = State.ENGAGED
            system.last_prompt = system.current_time
            system.add_state_log(event.timestamp, prev_state, system.current_state, event.event_type.name)
            print(f"[{system.current_time:.3f}] Driver STEERING_FORCE ({force:.1f}N) < VALID_RESPONSE_FORCE. Alarm escape. State changed from {prev_state.name} to {system.current_state.name}")
        else:
            print(f"[{system.current_time:.3f}] Driver STEERING_FORCE ({force:.1f}N) < VALID_RESPONSE_FORCE. No relevant state change from {system.current_state.name}.")
    else:
        # Ignored mid-range force while AwaitingResponse -> no-op, keep waiting
        print(f"[{system.current_time:.3f}] Driver STEERING_FORCE ({force:.1f}N). No relevant state change from {system.current_state.name}.")

def handle_lidar_sensor_event(system: SystemState, event: SensorEvent):
    # system.current_time is managed by run_simulation.
    if event.data_value < LIDAR_DANGER:
        system.emit_feature_decision(event.timestamp, FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.BRAKE)
        system.emit_command(event.timestamp, Actuator.BRAKING_SYSTEM)
        print(f"[{system.current_time:.3f}] Lidar ({event.data_value:.1f}) < LIDAR_DANGER. EMERGENCY_BRAKING (BRAKE) and BRAKING_SYSTEM command issued.")
    else:
        system.emit_feature_decision(event.timestamp, FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.NO_BRAKE)
        print(f"[{system.current_time:.3f}] Lidar ({event.data_value:.1f}) >= LIDAR_DANGER. EMERGENCY_BRAKING (NO_BRAKE).")

def handle_camera_sensor_event(system: SystemState, event: SensorEvent):
    # system.current_time is managed by run_simulation.
    if system.current_state == State.ENGAGED:
        system.emit_feature_decision(event.timestamp, FeatureDecisionKind.LANE_KEEPING, DecisionValue.ADJUST)
        system.emit_feature_decision(event.timestamp, FeatureDecisionKind.CRUISE_CONTROL, DecisionValue.ADJUST)
        system.emit_command(event.timestamp, Actuator.STEERING_MOTOR)
        system.emit_command(event.timestamp, Actuator.SPEED_ACTUATOR)
        print(f"[{system.current_time:.3f}] Camera detected in {system.current_state.name} state. LANE_KEEPING, CRUISE_CONTROL (ADJUST) and STEERING_MOTOR, SPEED_ACTUATOR commands issued.")
    else:
        print(f"[{system.current_time:.3f}] Camera detected in {system.current_state.name} state. No feature decisions or commands issued.")


# --- Internal Step ---

def internal_step(system: SystemState, current_simulation_time: float) -> bool:
    """
    Checks for and applies time-triggered internal state changes.
    Returns True if a state change occurred, False otherwise.
    """
    prev_state = system.current_state
    
    # Do not set system.current_time here, it's set by run_simulation
    # system.current_time = current_simulation_time

    if system.current_state == State.ENGAGED and \
       current_simulation_time >= system.last_prompt + PROMPT_INTERVAL:
        # Prompt: Engaged long enough since last prompt -> AwaitingResponse
        system.current_state = State.AWAITING_RESPONSE
        system.awaiting_since = current_simulation_time
        system.add_state_log(current_simulation_time, prev_state, system.current_state, "PROMPT_TIMEOUT")
        system.emit_command(current_simulation_time, Actuator.STEERING_MOTOR) # Command to nudge steering wheel
        print(f"[{current_simulation_time:.3f}] PROMPT_TIMEOUT: State changed from {prev_state.name} to {system.current_state.name}. Steering motor nudged.")
        return True # State changed

    elif system.current_state == State.AWAITING_RESPONSE and \
         current_simulation_time >= system.awaiting_since + RESPONSE_WINDOW:
        # Response timeout: AwaitingResponse longer than window -> Alarming
        system.current_state = State.ALARMING
        system.add_state_log(current_simulation_time, prev_state, system.current_state, "RESPONSE_TIMEOUT")
        system.emit_command(current_simulation_time, Actuator.ALARM_ACTUATOR)
        print(f"[{current_simulation_time:.3f}] RESPONSE_TIMEOUT: State changed from {prev_state.name} to {system.current_state.name}. Alarm triggered.")
        return True # State changed

    elif system.current_state == State.ALARMING:
        # Alarm tick: emit one alarm command per tick, but no state change
        system.emit_command(current_simulation_time, Actuator.ALARM_ACTUATOR)
        print(f"[{current_simulation_time:.3f}] ALARM_TICK: Emitting ALARM_ACTUATOR command.")
        return False # No state change

    return False # No internal state change


# --- Main Simulation Logic ---
# Smallest time increment for simulation, prevents infinite loops on identical timestamps
# and ensures internal events can "tick" when no external events are present.
TIME_EPSILON = 0.001

def run_simulation(input_dir: str, output_dir: str):
    print(f"Starting Copilot simulation with input from '{input_dir}' and output to '{output_dir}'")

    all_events_raw = []
    try:
        all_events_raw.extend(read_sensor_log(f"{input_dir}/sensor_log.csv"))
        all_events_raw.extend(read_driver_events(f"{input_dir}/driver_events.csv"))
    except FileNotFoundError as e:
        print(f"Error: Input file not found: {e}. Please ensure both sensor_log.csv and driver_events.csv exist in the input directory.")
        return
    except Exception as e:
        print(f"Error reading input files: {e}")
        return

    all_events_raw.sort(key=lambda x: x.timestamp) # Sort all events by timestamp

    system = SystemState()
    
    # Set initial system time to the first event's timestamp, or 0 if no events
    if all_events_raw:
        system.current_time = all_events_raw[0].timestamp
        system.last_prompt = system.current_time # Initialize last_prompt
    else:
        print("No events to process. Simulation ending.")
        # Ensure output directory exists even if no events
        import os
        os.makedirs(output_dir, exist_ok=True)
        write_state_log(f"{output_dir}/state_log.csv", system.state_log)
        write_commands_log(f"{output_dir}/commands_log.csv", system.commands_log)
        write_feature_decision_log(f"{output_dir}/feature_decision.csv", system.feature_decision_log)
        return

    print(f"[{system.current_time:.3f}] Initial state: {system.current_state.name}")

    event_queue = deque(all_events_raw)

    while event_queue or \
          system.current_state == State.ALARMING or \
          (system.current_state == State.ENGAGED and system.current_time < system.last_prompt + PROMPT_INTERVAL) or \
          (system.current_state == State.AWAITING_RESPONSE and system.current_time < system.awaiting_since + RESPONSE_WINDOW):

        next_external_event_time = float('inf')
        if event_queue:
            next_external_event_time = event_queue[0].timestamp

        next_prompt_check_time = float('inf')
        if system.current_state == State.ENGAGED:
            next_prompt_check_time = system.last_prompt + PROMPT_INTERVAL
        
        next_response_timeout_check_time = float('inf')
        if system.current_state == State.AWAITING_RESPONSE:
            next_response_timeout_check_time = system.awaiting_since + RESPONSE_WINDOW
        
        next_alarming_tick_time = float('inf')
        if system.current_state == State.ALARMING:
            # When alarming, we want to tick continuously, so the next event is a small time increment
            next_alarming_tick_time = system.current_time + TIME_EPSILON

        # Determine the next moment in time something significant happens
        next_significant_time = min(
            next_external_event_time,
            next_prompt_check_time,
            next_response_timeout_check_time,
            next_alarming_tick_time
        )
        
        if next_significant_time == float('inf'):
            break # No more events or triggers, simulation ends

        # Advance system time to the next significant point.
        # Ensure time only moves forward.
        if next_significant_time > system.current_time:
            system.current_time = next_significant_time
        elif next_significant_time < system.current_time:
            # This should ideally not happen if event sorting and min logic is correct.
            # If it does, it's a timestamp going backward, which is an error.
            # For robustness, we'll force it forward by a small epsilon.
            system.current_time += TIME_EPSILON
        # If next_significant_time == system.current_time, it means we are processing
        # something at the current timestamp, so system.current_time doesn't advance yet.
        # It will either be advanced by processing a later event, or by TIME_EPSILON if
        # no further events/triggers are at this timestamp in the next iteration.

        # Process external events that occurred at or before the current system time
        # Use a small buffer for float comparison to avoid issues with floating point precision.
        while event_queue and event_queue[0].timestamp <= system.current_time + TIME_EPSILON / 2: 
            event = event_queue.popleft()
            # Align current_time to event timestamp for precise logging if event is exactly at this time.
            system.current_time = max(system.current_time, event.timestamp) 
            process_event(system, event)
        
        # After processing external events up to current_time, check for internal steps
        # Pass system.current_time to internal_step for its logic.
        internal_step(system, system.current_time)

    print(f"[{system.current_time:.3f}] Simulation finished. Final state: {system.current_state.name}")
    print("Writing output logs...")

    # Ensure output directory exists
    import os
    os.makedirs(output_dir, exist_ok=True)

    write_state_log(f"{output_dir}/state_log.csv", system.state_log)
    write_commands_log(f"{output_dir}/commands_log.csv", system.commands_log)
    write_feature_decision_log(f"{output_dir}/feature_decision.csv", system.feature_decision_log)
    print("Output logs written.")


def process_event(system: SystemState, event: Event):
    """Dispatches event to appropriate handler."""
    # system.current_time is already updated by run_simulation
    if isinstance(event, SensorEvent):
        if event.sensor_type == SensorType.LIDAR:
            handle_lidar_sensor_event(system, event)
        elif event.sensor_type == SensorType.CAMERA:
            handle_camera_sensor_event(system, event)
    elif isinstance(event, DriverEvent):
        if event.event_type == DriverEventType.ENGAGE:
            handle_engage_driver_event(system, event)
        elif event.event_type == DriverEventType.DISENGAGE:
            handle_disengage_driver_event(system, event)
        elif event.event_type == DriverEventType.STEERING_FORCE:
            handle_steering_force_driver_event(system, event)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copilot - Advanced Driver Assistance System Simulation.")
    parser.add_argument("--input", required=True, help="Path to the input directory containing sensor_log.csv and driver_events.csv")
    parser.add_argument("--output", required=True, help="Path to the output directory for state_log.csv, commands_log.csv, and feature_decision.csv")
    
    args = parser.parse_args()

    run_simulation(args.input, args.output)
