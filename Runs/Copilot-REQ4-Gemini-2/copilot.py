import argparse
import csv
from dataclasses import dataclass, field
from enum import Enum
import os
import sys

# --- ENUMERATED DOMAINS ---
class State(Enum):
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

class FeatureDecisionKind(Enum):
    EMERGENCY_BRAKING = "EmergencyBraking"
    LANE_KEEPING = "LaneKeeping"
    CRUISE_CONTROL = "CruiseControl"

class DecisionValue(Enum):
    BRAKE = "BRAKE"
    NO_BRAKE = "NO_BRAKE"
    ADJUST = "ADJUST"

class Actuator(Enum):
    BRAKING_SYSTEM = "BrakingSystem"
    STEERING_MOTOR = "SteeringMotor"
    SPEED_ACTUATOR = "SpeedActuator"
    ALARM_ACTUATOR = "AlarmActuator"

# --- THRESHOLD CONSTANTS ---
LIDAR_DANGER = 5
OVERRIDE_FORCE = 10
VALID_RESPONSE_FORCE = 3
PROMPT_INTERVAL = 120 # Int only for Alloy modeling (float in input and output)
RESPONSE_WINDOW = 5

# --- LOG ENTRY CLASSES ---
@dataclass
class StateLogEntry:
    time: float
    previous_state: State
    current_state: State
    trigger_event: str # Name of the event that caused the state change

@dataclass
class Command:
    time: float
    actuator_id: Actuator
    values: str = "" # Some actuators might have values, some not

@dataclass
class FeatureDecision:
    time: float
    feature: FeatureDecisionKind
    decision: DecisionValue

# --- EVENT CLASSES ---
@dataclass
class Event:
    time: float
    original_line_num: int = 0 # For debugging/logging original input order

    def __lt__(self, other):
        return self.time < other.time

@dataclass
class SensorEvent(Event):
    sensor_type: SensorType
    data_value: float
    sensor_id: str = "" # From input file, not directly used in Alloy logic

@dataclass
class DriverEvent(Event):
    event_type: DriverEventType
    value: float = 0.0 # Force for STEERING_FORCE, or general value for other events


# --- SYSTEM STATE ---
@dataclass
class SystemState:
    current_state: State = State.DISENGAGED
    current_time: float = 0.0
    last_prompt: float = 0.0
    awaiting_since: float = 0.0

    state_log: list[StateLogEntry] = field(default_factory=list)
    commands_log: list[Command] = field(default_factory=list)
    feature_decision_log: list[FeatureDecision] = field(default_factory=list)

    processed_events: list[Event] = field(default_factory=list)

    def add_state_log(self, time: float, previous: State, current: State, trigger_event: str):
        self.state_log.append(StateLogEntry(time, previous, current, trigger_event))

    def emit_command(self, time: float, actuator: Actuator, values: str = ""):
        self.commands_log.append(Command(time, actuator, values))

    def emit_feature_decision(self, time: float, feature: FeatureDecisionKind, decision: DecisionValue):
        self.feature_decision_log.append(FeatureDecision(time, feature, decision))

    def get_logs(self):
        return self.state_log, self.commands_log, self.feature_decision_log

def parse_sensor_log(file_path: str) -> list[SensorEvent]:
    events = []
    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for i, row in enumerate(reader):
                try:
                    timestamp = float(row['timestamp'])
                    sensor_id = row['sensor_id']
                    sensor_type = SensorType(row['sensor_type'])
                    data_value = float(row['data_value'])
                    # unit = row['unit'] # Not used in logic, ignoring for now
                    events.append(SensorEvent(timestamp, i + 2, sensor_type, data_value, sensor_id))
                except (ValueError, KeyError) as e:
                    print(f"Warning: Skipping malformed sensor log entry at line {i+2} in {file_path}: {e}", file=sys.stderr)
    except FileNotFoundError:
        print(f"Error: sensor_log.csv not found at {file_path}", file=sys.stderr)
    return events

def parse_driver_events(file_path: str) -> list[DriverEvent]:
    events = []
    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for i, row in enumerate(reader):
                try:
                    timestamp = float(row['timestamp'])
                    event_type = DriverEventType(row['event_type'])
                    value = float(row['value']) if 'value' in row and row['value'] else 0.0 # Steering force might be 0
                    events.append(DriverEvent(timestamp, i + 2, event_type, value))
                except (ValueError, KeyError) as e:
                    print(f"Warning: Skipping malformed driver event entry at line {i+2} in {file_path}: {e}", file=sys.stderr)
    except FileNotFoundError:
        print(f"Error: driver_events.csv not found at {file_path}", file=sys.stderr)
    return events

def write_state_log(file_path: str, log: list[StateLogEntry]):
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['timestamp', 'previous_state', 'current_state', 'trigger_event']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for entry in log:
            writer.writerow({
                'timestamp': entry.time,
                'previous_state': entry.previous_state.value,
                'current_state': entry.current_state.value,
                'trigger_event': entry.trigger_event
            })

def write_commands_log(file_path: str, log: list[Command]):
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['timestamp', 'actuator_id', 'values']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for entry in log:
            writer.writerow({
                'timestamp': entry.time,
                'actuator_id': entry.actuator_id.value,
                'values': entry.values
            })

def write_feature_decision_log(file_path: str, log: list[FeatureDecision]):
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['timestamp', 'feature', 'decision']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for entry in log:
            writer.writerow({
                'timestamp': entry.time,
                'feature': entry.feature.value,
                'decision': entry.decision.value
            })

class Copilot:
    def __init__(self):
        self.system_state = SystemState()

    def _add_state_log(self, previous: State, current: State, trigger_event: str):
        self.system_state.add_state_log(self.system_state.current_time, previous, current, trigger_event)

    def _emit_command(self, actuator: Actuator, values: str = ""):
        self.system_state.emit_command(self.system_state.current_time, actuator, values)

    def _emit_feature_decision(self, feature: FeatureDecisionKind, decision: DecisionValue):
        self.system_state.emit_feature_decision(self.system_state.current_time, feature, decision)

    def _transition_state(self, new_state: State, trigger_event: str):
        if self.system_state.current_state != new_state:
            self._add_state_log(self.system_state.current_state, new_state, trigger_event)
            self.system_state.current_state = new_state

    def _handle_engage_driver_event(self, event: DriverEvent):
        # Disengaged -> Engaged
        if self.system_state.current_state == State.DISENGAGED:
            self._transition_state(State.ENGAGED, event.event_type.value)
            self.system_state.last_prompt = self.system_state.current_time
        # Other states -> no-op (as per Alloy model)

    def _handle_disengage_driver_event(self, event: DriverEvent):
        # Any non-Disengaged state -> Disengaged
        if self.system_state.current_state != State.DISENGAGED:
            self._transition_state(State.DISENGAGED, event.event_type.value)
        # Already Disengaged -> no-op

    def _handle_steering_force_driver_event(self, event: DriverEvent):
        force = event.value
        current_state = self.system_state.current_state

        # Override: force > OVERRIDE_FORCE, any state -> Disengaged (FR-04)
        if force > OVERRIDE_FORCE:
            self._transition_state(State.DISENGAGED, event.event_type.value)
        # Valid response while AwaitingResponse -> Engaged, reset prompt timer
        elif force <= VALID_RESPONSE_FORCE and current_state == State.AWAITING_RESPONSE:
            self._transition_state(State.ENGAGED, event.event_type.value)
            self.system_state.last_prompt = self.system_state.current_time
        # Alarm escape: low force while Alarming -> Engaged, reset prompt timer
        elif force <= VALID_RESPONSE_FORCE and current_state == State.ALARMING:
            self._transition_state(State.ENGAGED, event.event_type.value)
            self.system_state.last_prompt = self.system_state.current_time
        # Ignored mid-range force while AwaitingResponse -> no-op, keep waiting (implicit by not matching other conditions)
        # Other cases (e.g., low force in Disengaged/Engaged) -> no-op

    def _handle_lidar_sensor_event(self, event: SensorEvent):
        if event.data_value < LIDAR_DANGER:
            self._emit_feature_decision(FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.BRAKE)
            self._emit_command(Actuator.BRAKING_SYSTEM)
        else:
            self._emit_feature_decision(FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.NO_BRAKE)

    def _handle_camera_sensor_event(self, event: SensorEvent):
        if self.system_state.current_state == State.ENGAGED:
            self._emit_feature_decision(FeatureDecisionKind.LANE_KEEPING, DecisionValue.ADJUST)
            self._emit_feature_decision(FeatureDecisionKind.CRUISE_CONTROL, DecisionValue.ADJUST)
            self._emit_command(Actuator.STEERING_MOTOR)
            self._emit_command(Actuator.SPEED_ACTUATOR)

    def process_event(self, event: Event):
        # Update current time to event time if event time is greater
        if event.time > self.system_state.current_time:
            self.system_state.current_time = event.time
        # Tick the time if event.time == current_time this simulates that multiple events can be processed at the same logical point in time
        # This aligns with the Alloy model's "tickTime" within each handler.

        if isinstance(event, SensorEvent):
            if event.sensor_type == SensorType.LIDAR:
                self._handle_lidar_sensor_event(event)
            elif event.sensor_type == SensorType.CAMERA:
                self._handle_camera_sensor_event(event)
        elif isinstance(event, DriverEvent):
            if event.event_type == DriverEventType.ENGAGE:
                self._handle_engage_driver_event(event)
            elif event.event_type == DriverEventType.DISENGAGE:
                self._handle_disengage_driver_event(event)
            elif event.event_type == DriverEventType.STEERING_FORCE:
                self._handle_steering_force_driver_event(event)
        
        self.system_state.processed_events.append(event)


    def _execute_internal_logic_at_current_time(self) -> bool:
        """
        Executes internal logic checks (prompts, timeouts, alarms) at the current system time.
        Does NOT advance the system time.
        Returns True if any state or log changes occurred, False otherwise.
        """
        initial_state = self.system_state.current_state
        initial_state_log_len = len(self.system_state.state_log)
        initial_commands_log_len = len(self.system_state.commands_log)
        initial_feature_decision_log_len = len(self.system_state.feature_decision_log)

        # Check for prompt interval
        if (self.system_state.current_state == State.ENGAGED and
                (self.system_state.current_time - self.system_state.last_prompt) >= PROMPT_INTERVAL):
            self._transition_state(State.AWAITING_RESPONSE, "Attentiveness Check Prompt")
            self.system_state.awaiting_since = self.system_state.current_time
            self._emit_command(Actuator.STEERING_MOTOR, "Prompt Driver")
            return True

        # Check for response timeout
        if (self.system_state.current_state == State.AWAITING_RESPONSE and
                (self.system_state.current_time - self.system_state.awaiting_since) >= RESPONSE_WINDOW):
            self._transition_state(State.ALARMING, "Attentiveness Timeout")
            self._emit_command(Actuator.ALARM_ACTUATOR)
            return True
        
        # Alarm tick (keep alarming, emit one alarm command per tick)
        if self.system_state.current_state == State.ALARMING:
            self._emit_command(Actuator.ALARM_ACTUATOR)
            return True # Emitting a command counts as a change
            
        # Check if anything changed
        return (initial_state != self.system_state.current_state or
                len(self.system_state.state_log) != initial_state_log_len or
                len(self.system_state.commands_log) != initial_commands_log_len or
                len(self.system_state.feature_decision_log) != initial_feature_decision_log_len)

    def run_simulation(self, all_events: list[Event]):
        all_events.sort(key=lambda e: e.time)
        
        # Group events by their integer timestamp for discrete processing
        events_by_int_time = {}
        max_event_int_time = 0
        if all_events:
            for event in all_events:
                int_time = int(event.time)
                if int_time not in events_by_int_time:
                    events_by_int_time[int_time] = []
                events_by_int_time[int_time].append(event)
            max_event_int_time = int(all_events[-1].time)

        current_tick = 0 
        
        # Safety break to prevent infinite loops in simulations that might not naturally terminate
        MAX_TICKS_AFTER_LAST_EVENT = max(PROMPT_INTERVAL, RESPONSE_WINDOW) + 200 # Sufficient buffer

        while True:
            # 1. Update current system time to the current discrete tick
            self.system_state.current_time = float(current_tick)

            # 2. Process all external events that occur at the current_tick
            if current_tick in events_by_int_time:
                events_at_this_time = sorted(events_by_int_time[current_tick], key=lambda e: e.original_line_num)
                for event in events_at_this_time:
                    self.process_event(event)

            # 3. Execute internal logic (prompts, timeouts, alarms)
            # Loop to handle any chained internal state changes that might occur at the same tick
            made_internal_change_this_tick = True
            while made_internal_change_this_tick:
                made_internal_change_this_tick = self._execute_internal_logic_at_current_time()

            # 4. Check for termination conditions
            # The simulation should stop if:
            #   a) All external events have been processed (current_tick > max_event_int_time) AND
            #   b) The system is in a stable, non-active state (Disengaged, or Alarming for too long without new events)
            
            # Condition (a) check: Have all external events with int_time <= current_tick been processed?
            all_external_events_processed_up_to_current_tick = (current_tick > max_event_int_time)

            if all_external_events_processed_up_to_current_tick:
                if self.system_state.current_state == State.DISENGAGED:
                    # If disengaged and no more events, simulation ends
                    break
                elif self.system_state.current_state == State.ALARMING:
                    # If alarming, it could run forever. Break if it's been alarming for a long time
                    # after all external events, preventing infinite loops.
                    if current_tick > max_event_int_time + MAX_TICKS_AFTER_LAST_EVENT:
                        break
                elif self.system_state.current_state == State.ENGAGED or \
                     self.system_state.current_state == State.AWAITING_RESPONSE:
                    # These states can still transition internally (to AWAITING_RESPONSE or ALARMING)
                    # Allow a buffer for these transitions to play out.
                    if current_tick > max_event_int_time + MAX_TICKS_AFTER_LAST_EVENT:
                         break # Safety break if it's engaged/awaiting and runs too long without external events

            current_tick += 1

        print("Simulation complete.")


def main():
    parser = argparse.ArgumentParser(description="Copilot - Advanced Driver Assistance Simulation")
    parser.add_argument("--input", required=True, help="Path to the input directory containing sensor_log.csv and driver_events.csv")
    parser.add_argument("--output", required=True, help="Path to the output directory for state_log.csv, commands_log.csv, and feature_decision.csv")
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    if not os.path.isdir(input_dir):
        print(f"Error: Input directory '{input_dir}' not found.", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    elif not os.path.isdir(output_dir):
        print(f"Error: Output path '{output_dir}' exists but is not a directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Reading sensor events from {os.path.join(input_dir, 'sensor_log.csv')}")
    sensor_events = parse_sensor_log(os.path.join(input_dir, 'sensor_log.csv'))
    print(f"Reading driver events from {os.path.join(input_dir, 'driver_events.csv')}")
    driver_events = parse_driver_events(os.path.join(input_dir, 'driver_events.csv'))

    all_events = sensor_events + driver_events
    print(f"Total events loaded: {len(all_events)}")

    copilot_sim = Copilot()
    copilot_sim.run_simulation(all_events)

    state_log, commands_log, feature_decision_log = copilot_sim.system_state.get_logs()

    print(f"Writing state log to {os.path.join(output_dir, 'state_log.csv')}")
    write_state_log(os.path.join(output_dir, 'state_log.csv'), state_log)
    print(f"Writing commands log to {os.path.join(output_dir, 'commands_log.csv')}")
    write_commands_log(os.path.join(output_dir, 'commands_log.csv'), commands_log)
    print(f"Writing feature decision log to {os.path.join(output_dir, 'feature_decision.csv')}")
    write_feature_decision_log(os.path.join(output_dir, 'feature_decision.csv'), feature_decision_log)

    print("Copilot simulation finished successfully.")

if __name__ == "__main__":
    main()
