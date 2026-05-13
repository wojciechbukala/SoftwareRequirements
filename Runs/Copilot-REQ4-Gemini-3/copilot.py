import argparse
import csv
import os
import sys
from enum import Enum, auto

# 1. Enums and Constants (from Alloy model)

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

# Threshold constants
LIDAR_DANGER = 5.0
OVERRIDE_FORCE = 10.0
VALID_RESPONSE_FORCE = 3.0
PROMPT_INTERVAL = 120.0
RESPONSE_WINDOW = 5.0

# 2. Data Structures for logs (from Alloy model)

class StateLogEntry:
    def __init__(self, time: float, previous: State, current: State, trigger_event: str = "INTERNAL"):
        self.time = time
        self.previous = previous
        self.current = current
        self.trigger_event = trigger_event

class Command:
    def __init__(self, time: float, target: Actuator, value: str = ""):
        self.time = time
        self.target = target
        self.value = value # For future extensibility if actuators need values

class FeatureDecision:
    def __init__(self, time: float, feature: FeatureDecisionKind, value: DecisionValue):
        self.time = time
        self.feature = feature
        self.value = value

# 3. Event Models (from Alloy model)

class Event:
    def __init__(self, time: float):
        self.time = time

class SensorEvent(Event):
    def __init__(self, time: float, sensor_type: SensorType, data_value: float):
        super().__init__(time)
        self.sensor_type = sensor_type
        self.data_value = data_value

class DriverEvent(Event):
    def __init__(self, time: float, event_type: DriverEventType, force: float = None):
        super().__init__(time)
        self.event_type = event_type
        self.force = force

# 4. System State

class SystemState:
    """
    Represents the core system state as defined in the Alloy model.
    All mutable attributes are explicitly tracked.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SystemState, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.current_state = State.DISENGAGED
        self.current_time = 0.0
        self.last_prompt = 0.0
        self.awaiting_since = 0.0

        self.state_log = []
        self.commands_log = []
        self.feature_decision_log = []

        self.processed_events_times = set() # Store event times to mark them as processed

    def reset(self):
        """Resets the system state to its initial configuration."""
        self.current_state = State.DISENGAGED
        self.current_time = 0.0
        self.last_prompt = 0.0
        self.awaiting_since = 0.0

        self.state_log = []
        self.commands_log = []
        self.feature_decision_log = []

        self.processed_events_times = set()

    def add_state_log_entry(self, time: float, previous: State, current: State, trigger_event: str = "INTERNAL"):
        if previous != current: # Only log actual state transitions
            self.state_log.append(StateLogEntry(time, previous, current, trigger_event))

    def emit_command(self, time: float, target: Actuator, value: str = ""):
        self.commands_log.append(Command(time, target, value))

    def emit_feature_decision(self, time: float, feature: FeatureDecisionKind, value: DecisionValue):
        self.feature_decision_log.append(FeatureDecision(time, feature, value))

    def mark_event_processed(self, event_time: float):
        self.processed_events_times.add(event_time)

    def is_event_processed(self, event_time: float) -> bool:
        return event_time in self.processed_events_times

# 5. Event Handlers (based on Alloy predicates)

def _handle_engage_driver_event(system_state: SystemState, event: DriverEvent):
    """Handles ENGAGE driver events."""
    prev_state = system_state.current_state
    if prev_state == State.DISENGAGED:
        system_state.current_state = State.ENGAGED
        system_state.last_prompt = event.time # Reset prompt timer
        system_state.add_state_log_entry(event.time, prev_state, system_state.current_state, "ENGAGE_EVENT")
    # If already engaged, no state change, but time still ticks and event is processed.


def _handle_disengage_driver_event(system_state: SystemState, event: DriverEvent):
    """Handles DISENGAGE driver events."""
    prev_state = system_state.current_state
    if prev_state != State.DISENGAGED:
        system_state.current_state = State.DISENGAGED
        system_state.add_state_log_entry(event.time, prev_state, system_state.current_state, "DISENGAGE_EVENT")


def _handle_steering_force_driver_event(system_state: SystemState, event: DriverEvent):
    """Handles STEERING_FORCE driver events."""
    force = event.force
    prev_state = system_state.current_state

    # Override: force > OVERRIDE_FORCE, any state -> Disengaged (FR-04)
    if force > OVERRIDE_FORCE:
        if prev_state != State.DISENGAGED:
            system_state.current_state = State.DISENGAGED
            system_state.add_state_log_entry(event.time, prev_state, system_state.current_state, "OVERRIDE_EVENT")
    # Valid response while AwaitingResponse -> Engaged, reset prompt timer
    elif force <= VALID_RESPONSE_FORCE and prev_state == State.AWAITING_RESPONSE:
        system_state.current_state = State.ENGAGED
        system_state.last_prompt = event.time
        system_state.add_state_log_entry(event.time, prev_state, system_state.current_state, "VALID_RESPONSE")
    # Alarm escape: low force while Alarming -> Engaged, reset prompt timer
    elif force <= VALID_RESPONSE_FORCE and prev_state == State.ALARMING:
        system_state.current_state = State.ENGAGED
        system_state.last_prompt = event.time
        system_state.add_state_log_entry(event.time, prev_state, system_state.current_state, "ALARM_ESCAPE")
    # Otherwise, no state change for mid-range force in AwaitingResponse or other cases.


def _handle_lidar_sensor_event(system_state: SystemState, event: SensorEvent):
    """Handles LIDAR sensor events, focusing on emergency braking."""
    if event.data_value < LIDAR_DANGER:
        system_state.emit_feature_decision(event.time, FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.BRAKE)
        system_state.emit_command(event.time, Actuator.BRAKING_SYSTEM)
    else:
        system_state.emit_feature_decision(event.time, FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.NO_BRAKE)


def _handle_camera_sensor_event(system_state: SystemState, event: SensorEvent):
    """Handles CAMERA sensor events, for lane keeping and cruise control."""
    if system_state.current_state == State.ENGAGED:
        system_state.emit_feature_decision(event.time, FeatureDecisionKind.LANE_KEEPING, DecisionValue.ADJUST)
        system_state.emit_feature_decision(event.time, FeatureDecisionKind.CRUISE_CONTROL, DecisionValue.ADJUST)
        system_state.emit_command(event.time, Actuator.STEERING_MOTOR)
        system_state.emit_command(event.time, Actuator.SPEED_ACTUATOR)

# 6. Core Simulation Logic

def _process_event(system_state: SystemState, event: Event):
    """
    Processes a single external event. It advances the system's time to the event's timestamp,
    then dispatches the event to the appropriate handler based on its type (SensorEvent or DriverEvent).
    Finally, it marks the event as processed.
    """
    system_state.current_time = event.time # Advance time to event's time

    if isinstance(event, SensorEvent):
        if event.sensor_type == SensorType.LIDAR:
            _handle_lidar_sensor_event(system_state, event)
        elif event.sensor_type == SensorType.CAMERA:
            _handle_camera_sensor_event(system_state, event)
    elif isinstance(event, DriverEvent):
        if event.event_type == DriverEventType.ENGAGE:
            _handle_engage_driver_event(system_state, event)
        elif event.event_type == DriverEventType.DISENGAGE:
            _handle_disengage_driver_event(system_state, event)
        elif event.event_type == DriverEventType.STEERING_FORCE:
            _handle_steering_force_driver_event(system_state, event)
    
    system_state.mark_event_processed(event.time)


def _apply_internal_logic(system_state: SystemState, current_simulation_time: float):
    """
    Applies internal system logic (e.g., attentiveness checks, timeouts) as described
    by the 'internalStep' predicate in the Alloy model. These can change state
    even without an explicit external event. This function is called when the
    simulation time advances to a point where internal logic might trigger.
    """
    # Only apply internal logic if we are "in between" discrete events,
    # or if we need to catch up internal state to current simulation time.
    # We should avoid re-applying logic for a time point already covered.

    prev_state = system_state.current_state

    # Prompt interval check: Engaged -> AwaitingResponse
    if (prev_state == State.ENGAGED and
            (current_simulation_time - system_state.last_prompt) >= PROMPT_INTERVAL):
        system_state.current_state = State.AWAITING_RESPONSE
        system_state.awaiting_since = current_simulation_time
        system_state.add_state_log_entry(current_simulation_time, prev_state, system_state.current_state, "PROMPT_TIMEOUT")
        system_state.emit_command(current_simulation_time, Actuator.STEERING_MOTOR, "PROMPT_STEER") # Steering nudge for prompt

    prev_state = system_state.current_state # Update prev_state in case it changed

    # Response window check: AwaitingResponse -> Alarming
    if (prev_state == State.AWAITING_RESPONSE and
            (current_simulation_time - system_state.awaiting_since) >= RESPONSE_WINDOW):
        system_state.current_state = State.ALARMING
        system_state.add_state_log_entry(current_simulation_time, prev_state, system_state.current_state, "RESPONSE_TIMEOUT")
        system_state.emit_command(current_simulation_time, Actuator.ALARM_ACTUATOR)

    # Alarming state: The emission of alarm commands per tick will be handled in the main simulation loop.
    # This function is primarily for state transitions and their immediate commands.


    pass # system_state.current_time is managed by the simulate loop


def simulate(input_dir: str, output_dir: str):
    """
    Main simulation function. Reads events, processes them, and writes logs.
    """
    system_state = SystemState()
    system_state.reset() # Ensure a clean slate for each simulation run

    # Read input files
    sensor_events = _read_sensor_log(os.path.join(input_dir, "sensor_log.csv"))
    driver_events = _read_driver_events(os.path.join(input_dir, "driver_events.csv"))

    # Combine and sort all events by timestamp
    all_events = sorted(sensor_events + driver_events, key=lambda e: e.time)

    event_index = 0

    while True:
        # Step 1: Determine the time of the next external event.
        # If no more external events, set to infinity to prioritize internal triggers.
        next_external_event = all_events[event_index] if event_index < len(all_events) else None
        next_external_event_time = next_external_event.time if next_external_event else float('inf')

        # Step 2: Determine the times for internal logic triggers, based on Alloy predicates.
        # PROMPT_INTERVAL for Engaged -> AwaitingResponse transition.
        next_prompt_trigger_time = float('inf')
        if system_state.current_state == State.ENGAGED:
            next_prompt_trigger_time = system_state.last_prompt + PROMPT_INTERVAL

        # RESPONSE_WINDOW for AwaitingResponse -> Alarming transition.
        next_response_timeout_time = float('inf')
        if system_state.current_state == State.AWAITING_RESPONSE:
            next_response_timeout_time = system_state.awaiting_since + RESPONSE_WINDOW
        
        # Step 3: Find the earliest significant time point (next tick in the simulation).
        next_time = min(next_external_event_time, next_prompt_trigger_time, next_response_timeout_time)

        # Step 4: If no more events or internal triggers are scheduled, terminate the simulation.
        if next_time == float('inf'):
            break
        
        # Step 5: Advance the system's current time to the earliest significant point.
        # This ensures that all events (external or internal) are processed in chronological order.
        if next_time > system_state.current_time:
            system_state.current_time = next_time
            # Apply internal logic for state transitions at this new time.
            _apply_internal_logic(system_state, system_state.current_time)
        elif next_time < system_state.current_time:
            # This condition indicates a potential issue with event sorting or time advancement.
            # In a correctly ordered simulation, time should never go backward.
            pass # Already processed this time or an earlier time, no action needed.


        # Step 6: Process any external event that occurs at the current system time.
        if next_external_event and next_external_event.time == system_state.current_time:
            _process_event(system_state, next_external_event)
            event_index += 1
        
        # Step 7: Handle continuous alarming. If the system is in the Alarming state,
        # an alarm command is emitted at each distinct time step, as per the Alloy model's "alarm tick".
        if system_state.current_state == State.ALARMING:
            system_state.emit_command(system_state.current_time, Actuator.ALARM_ACTUATOR)


    # Final internal logic application to catch anything up to the very last external event time + a small buffer
    # This might be redundant if the loop condition and internal logic are perfect.
    # It ensures that if the last external event was at T, and an internal trigger was at T+1, it's caught.
    # The loop `while True` and breaking condition should handle this.

    # Write output files
    _write_state_log(os.path.join(output_dir, "state_log.csv"), system_state.state_log)
    _write_commands_log(os.path.join(output_dir, "commands_log.csv"), system_state.commands_log)
    _write_feature_decision_log(os.path.join(output_dir, "feature_decision.csv"), system_state.feature_decision_log)

    print(f"Simulation complete. Logs written to {output_dir}")
    print(f"Final State: {system_state.current_state.name} at Time: {system_state.current_time}")


# 7. CSV Reading and Writing Utilities

def _read_sensor_log(file_path: str) -> list[SensorEvent]:
    """Reads sensor events from a CSV file."""
    events = []
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                time = float(row['timestamp'])
                sensor_type_str = row['sensor_type'].upper()
                sensor_type = SensorType[sensor_type_str]
                data_value = float(row['data_value'])
                events.append(SensorEvent(time, sensor_type, data_value))
    except FileNotFoundError:
        print(f"Warning: sensor_log.csv not found at {file_path}. No sensor events will be processed.", file=sys.stderr)
    except Exception as e:
        print(f"Error reading sensor_log.csv: {e}", file=sys.stderr)
        sys.exit(1)
    return events

def _read_driver_events(file_path: str) -> list[DriverEvent]:
    """Reads driver events from a CSV file."""
    events = []
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                time = float(row['timestamp'])
                event_type_str = row['event_type'].upper()
                event_type = DriverEventType[event_type_str]
                force = float(row['value']) if row['value'] else None
                events.append(DriverEvent(time, event_type, force))
    except FileNotFoundError:
        print(f"Warning: driver_events.csv not found at {file_path}. No driver events will be processed.", file=sys.stderr)
    except Exception as e:
        print(f"Error reading driver_events.csv: {e}", file=sys.stderr)
        sys.exit(1)
    return events

def _write_state_log(file_path: str, log_entries: list[StateLogEntry]):
    """Writes state log entries to a CSV file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'previous_state', 'current_state', 'trigger_event'])
        for entry in log_entries:
            writer.writerow([entry.time, entry.previous.name, entry.current.name, entry.trigger_event])

def _write_commands_log(file_path: str, log_entries: list[Command]):
    """Writes command log entries to a CSV file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'actuator_id', 'value'])
        for entry in log_entries:
            writer.writerow([entry.time, entry.target.name, entry.value])

def _write_feature_decision_log(file_path: str, log_entries: list[FeatureDecision]):
    """Writes feature decision log entries to a CSV file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'feature', 'decision'])
        for entry in log_entries:
            writer.writerow([entry.time, entry.feature.name, entry.value.name])

# 8. Main execution block for CLI

def main():
    parser = argparse.ArgumentParser(description="Copilot: Advanced Driver Assistance Simulation.")
    parser.add_argument("--input", type=str, required=True,
                        help="Path to the input directory containing sensor_log.csv and driver_events.csv.")
    parser.add_argument("--output", type=str, required=True,
                        help="Path to the output directory where state_log.csv, commands_log.csv, and feature_decision.csv will be written.")
    args = parser.parse_args()

    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)

    print(f"Starting Copilot simulation with input: {args.input}, output: {args.output}")
    simulate(args.input, args.output)
    print("Copilot simulation finished.")

if __name__ == "__main__":
    main()
