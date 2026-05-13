import argparse
import csv
from enum import Enum
import os

# --- Enums from Alloy model ---

class State(Enum):
    """Represents the operational states of the Copilot system."""
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"

class SensorType(Enum):
    """Represents the types of sensors providing data."""
    LIDAR = "Lidar"
    CAMERA = "Camera"

class DriverEventType(Enum):
    """Represents the types of driver interactions."""
    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"

class FeatureDecisionKind(Enum):
    """Represents the kinds of autonomous feature decisions."""
    EMERGENCY_BRAKING = "EmergencyBraking"
    LANE_KEEPING = "LaneKeeping"
    CRUISE_CONTROL = "CruiseControl"

class DecisionValue(Enum):
    """Represents the values of autonomous decisions."""
    BRAKE = "BRAKE"
    NO_BRAKE = "NO_BRAKE"
    ADJUST = "ADJUST"

class Actuator(Enum):
    """Represents the physical actuators controlled by the system."""
    BRAKING_SYSTEM = "BrakingSystem"
    STEERING_MOTOR = "SteeringMotor"
    SPEED_ACTUATOR = "SpeedActuator"
    ALARM_ACTUATOR = "AlarmActuator"

# --- Threshold Constants from Alloy model ---
LIDAR_DANGER = 5
OVERRIDE_FORCE = 10
VALID_RESPONSE_FORCE = 3
PROMPT_INTERVAL = 120
RESPONSE_WINDOW = 5

# --- Data Structures (corresponding to Alloy signatures) ---

class Event:
    """Base class for all system events."""
    def __init__(self, time: int):
        self.time = time

    def __lt__(self, other):
        return self.time < other.time

class SensorEvent(Event):
    """Represents data received from a sensor."""
    def __init__(self, time: int, sensor_type: SensorType, data_value: int, sensor_id: str = "N/A", unit: str = "N/A"):
        super().__init__(time)
        self.sensor_id = sensor_id
        self.sensor_type = sensor_type
        self.data_value = data_value
        self.unit = unit

class DriverEvent(Event):
    """Represents an interaction from the driver."""
    def __init__(self, time: int, event_type: DriverEventType, force: int = None):
        super().__init__(time)
        self.event_type = event_type
        self.force = force

class StateLogEntry:
    """Records a change in the system's operational state."""
    def __init__(self, time: int, previous: State, current: State, trigger_event: str = "INTERNAL"):
        self.time = time
        self.previous = previous
        self.current = current
        self.trigger_event = trigger_event

class Command:
    """Records a command issued to an actuator."""
    def __init__(self, time: int, target: Actuator, values: str = "N/A"):
        self.time = time
        self.target = target
        self.values = values

class FeatureDecision:
    """Records a decision made by an autonomous feature."""
    def __init__(self, time: int, feature: FeatureDecisionKind, value: DecisionValue):
        self.time = time
        self.feature = feature
        self.value = value

class SystemState:
    """
    Manages the current state of the Copilot system and logs all significant events,
    commands, and decisions.
    """
    def __init__(self):
        self.current_state: State = State.DISENGAGED
        self.current_time: int = 0
        self.last_prompt: int = 0
        self.awaiting_since: int = 0

        self.state_log: list[StateLogEntry] = []
        self.commands_log: list[Command] = []
        self.feature_decision_log: list[FeatureDecision] = []
        self.processed_events: list[Event] = []

    def _add_state_log(self, time: int, previous: State, current: State, trigger_event: str = "INTERNAL"):
        """Appends a new state log entry."""
        self.state_log.append(StateLogEntry(time, previous, current, trigger_event))
        print(f"[{time}] STATE CHANGE: {previous.value} -> {current.value}")

    def _emit_command(self, time: int, target: Actuator, values: str = "N/A"):
        """Appends a new command log entry."""
        self.commands_log.append(Command(time, target, values))
        print(f"[{time}] COMMAND: {target.value} ({values})")

    def _emit_feature_decision(self, time: int, feature: FeatureDecisionKind, value: DecisionValue):
        """Appends a new feature decision log entry."""
        self.feature_decision_log.append(FeatureDecision(time, feature, value))
        print(f"[{time}] DECISION: {feature.value} = {value.value}")

    def _tick_time(self):
        """Advances the internal system clock by one unit."""
        self.current_time += 1

    def _process_event(self, event: Event):
        """Marks an event as processed."""
        self.processed_events.append(event)

    def handle_engage_driver_event(self, event: DriverEvent):
        """Handles a driver ENGAGE event."""
        self._process_event(event)
        self._tick_time()

        if self.current_state == State.DISENGAGED:
            self._add_state_log(event.time, State.DISENGAGED, State.ENGAGED, event.event_type.value)
            self.current_state = State.ENGAGED
            self.last_prompt = self.current_time # Reset prompt timer
        # If already engaged or other state, ignore ENGAGE

    def handle_disengage_driver_event(self, event: DriverEvent):
        """Handles a driver DISENGAGE event."""
        self._process_event(event)
        self._tick_time()

        if self.current_state != State.DISENGAGED:
            self._add_state_log(event.time, self.current_state, State.DISENGAGED, event.event_type.value)
            self.current_state = State.DISENGAGED
        # If already disengaged, ignore DISENGAGE

    def handle_steering_force_driver_event(self, event: DriverEvent):
        """Handles a driver STEERING_FORCE event."""
        self._process_event(event)
        self._tick_time()

        force = event.force
        if force is None: # Should not happen based on Alloy, but for robustness
            return

        # FR-04: Override -> Disengaged
        if force > OVERRIDE_FORCE:
            if self.current_state != State.DISENGAGED:
                self._add_state_log(event.time, self.current_state, State.DISENGAGED, event.event_type.value)
                self.current_state = State.DISENGAGED
        elif self.current_state == State.AWAITING_RESPONSE and force <= VALID_RESPONSE_FORCE:
            # Valid response while AwaitingResponse -> Engaged
            self._add_state_log(event.time, State.AWAITING_RESPONSE, State.ENGAGED, event.event_type.value)
            self.current_state = State.ENGAGED
            self.last_prompt = self.current_time # Reset prompt timer
        elif self.current_state == State.ALARMING and force <= VALID_RESPONSE_FORCE:
            # Alarm escape -> Engaged
            self._add_state_log(event.time, State.ALARMING, State.ENGAGED, event.event_type.value)
            self.current_state = State.ENGAGED
            self.last_prompt = self.current_time # Reset prompt timer
        # Other cases: ignored (mid-range force in AwaitingResponse, low force in Disengaged/Engaged)

    def handle_lidar_sensor_event(self, event: SensorEvent):
        """Handles a Lidar sensor event, primarily for emergency braking."""
        self._process_event(event)
        self._tick_time()

        if event.data_value < LIDAR_DANGER:
            self._emit_feature_decision(event.time, FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.BRAKE)
            self._emit_command(event.time, Actuator.BRAKING_SYSTEM)
        else:
            self._emit_feature_decision(event.time, FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.NO_BRAKE)

    def handle_camera_sensor_event(self, event: SensorEvent):
        """Handles a Camera sensor event, primarily for lane keeping and cruise control."""
        self._process_event(event)
        self._tick_time()

        if self.current_state == State.ENGAGED:
            self._emit_feature_decision(event.time, FeatureDecisionKind.LANE_KEEPING, DecisionValue.ADJUST)
            self._emit_feature_decision(event.time, FeatureDecisionKind.CRUISE_CONTROL, DecisionValue.ADJUST)
            self._emit_command(event.time, Actuator.STEERING_MOTOR)
            self._emit_command(event.time, Actuator.SPEED_ACTUATOR)

    def internal_step(self):
        """
        Handles time-based internal state transitions (e.g., attentiveness prompts,
        response timeouts, alarming).
        """
        self._tick_time()

        # Prompt: Engaged -> AwaitingResponse
        if self.current_state == State.ENGAGED and 
           self.current_time >= self.last_prompt + PROMPT_INTERVAL:
            self._add_state_log(self.current_time, State.ENGAGED, State.AWAITING_RESPONSE)
            self.current_state = State.AWAITING_RESPONSE
            self.awaiting_since = self.current_time
            self._emit_command(self.current_time, Actuator.STEERING_MOTOR, "Prompt for attentiveness") # Alloy implies SteeringMotor
        # Response timeout: AwaitingResponse -> Alarming
        elif self.current_state == State.AWAITING_RESPONSE and 
             self.current_time >= self.awaiting_since + RESPONSE_WINDOW:
            self._add_state_log(self.current_time, State.AWAITING_RESPONSE, State.ALARMING)
            self.current_state = State.ALARMING
            self._emit_command(self.current_time, Actuator.ALARM_ACTUATOR)
        # Alarm tick: Keep Alarming, emit alarm command
        elif self.current_state == State.ALARMING:
            self._emit_command(self.current_time, Actuator.ALARM_ACTUATOR)
        # Otherwise, no state change, just time tick (stutter)

    def process_next_event(self, next_event: Event):
        """Processes the next external event."""
        # Ensure system time advances to at least the event time
        while self.current_time < next_event.time:
            self.internal_step()

        # Process the external event
        if isinstance(next_event, SensorEvent):
            if next_event.sensor_type == SensorType.LIDAR:
                self.handle_lidar_sensor_event(next_event)
            elif next_event.sensor_type == SensorType.CAMERA:
                self.handle_camera_sensor_event(next_event)
        elif isinstance(next_event, DriverEvent):
            if next_event.event_type == DriverEventType.ENGAGE:
                self.handle_engage_driver_event(next_event)
            elif next_event.event_type == DriverEventType.DISENGAGE:
                self.handle_disengage_driver_event(next_event)
            elif next_event.event_type == DriverEventType.STEERING_FORCE:
                self.handle_steering_force_driver_event(next_event)
        
        # After processing the event, if current_time is still at next_event.time,
        # perform an internal step to handle any immediate time-based transitions
        # that might be triggered at this exact time (e.g., prompt or timeout
        # if event time aligns).
        if self.current_time == next_event.time:
            self.internal_step()

    def finalize_processing(self):
        """Continues internal steps until all time-based events are resolved or no longer active."""
        # Continue internal steps as long as there are pending time-based actions
        # (like prompting or alarming)
        previous_state = None
        while (self.current_state == State.ENGAGED and self.current_time < self.last_prompt + PROMPT_INTERVAL) or 
              (self.current_state == State.AWAITING_RESPONSE and self.current_time < self.awaiting_since + RESPONSE_WINDOW) or 
              self.current_state == State.ALARMING:
            previous_state = self.current_state
            self.internal_step()
            if previous_state == self.current_state and self.current_state != State.ALARMING:
                # If state doesn't change and not alarming, nothing more will happen
                break


def read_sensor_log(file_path: str) -> list[SensorEvent]:
    """Reads sensor events from a CSV file."""
    events = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                time = int(row['timestamp'])
                sensor_id = row['sensor_id']
                sensor_type = SensorType(row['sensor_type'])
                data_value = int(row['data_value'])
                unit = row['unit']
                events.append(SensorEvent(time, sensor_type, data_value, sensor_id, unit))
            except (ValueError, KeyError) as e:
                print(f"Error reading sensor_log.csv row: {row} - {e}")
    return events

def read_driver_events(file_path: str) -> list[DriverEvent]:
    """Reads driver events from a CSV file."""
    events = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                time = int(row['timestamp'])
                event_type = DriverEventType(row['event_type'])
                force = int(row['value']) if row['value'] else None # 'value' column used for force
                events.append(DriverEvent(time, event_type, force))
            except (ValueError, KeyError) as e:
                print(f"Error reading driver_events.csv row: {row} - {e}")
    return events

def write_state_log(file_path: str, state_log: list[StateLogEntry]):
    """Writes the state log to a CSV file."""
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'previous_state', 'current_state', 'trigger_event'])
        for entry in state_log:
            writer.writerow([entry.time, entry.previous.value, entry.current.value, entry.trigger_event])

def write_commands_log(file_path: str, commands_log: list[Command]):
    """Writes the commands log to a CSV file."""
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'actuator_id', 'values'])
        for entry in commands_log:
            writer.writerow([entry.time, entry.target.value, entry.values])

def write_feature_decision_log(file_path: str, feature_decision_log: list[FeatureDecision]):
    """Writes the feature decision log to a CSV file."""
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'feature', 'decision'])
        for entry in feature_decision_log:
            writer.writerow([entry.time, entry.feature.value, entry.value.value])

def main():
    parser = argparse.ArgumentParser(description="Copilot: Autonomous Driver Assistance System Simulator")
    parser.add_argument("--input", required=True, help="Path to the input directory containing sensor_log.csv and driver_events.csv")
    parser.add_argument("--output", required=True, help="Path to the output directory for state_log.csv, commands_log.csv, and feature_decision.csv")
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
        print(f"Error: Output path '{output_dir}' is not a directory.")
        return

    sensor_log_path = os.path.join(input_dir, "sensor_log.csv")
    driver_events_path = os.path.join(input_dir, "driver_events.csv")

    if not os.path.isfile(sensor_log_path):
        print(f"Warning: sensor_log.csv not found in '{input_dir}'. Proceeding without sensor data.")
        sensor_events = []
    else:
        sensor_events = read_sensor_log(sensor_log_path)

    if not os.path.isfile(driver_events_path):
        print(f"Warning: driver_events.csv not found in '{input_dir}'. Proceeding without driver data.")
        driver_events = []
    else:
        driver_events = read_driver_events(driver_events_path)

    all_events = sorted(sensor_events + driver_events)

    copilot_system = SystemState()
    print("Copilot simulation started.")

    for event in all_events:
        print(f"
Processing event at time {event.time}: {type(event).__name__}")
        copilot_system.process_next_event(event)

    print("
All external events processed. Finalizing internal state transitions...")
    copilot_system.finalize_processing()
    print("Copilot simulation finished.")

    write_state_log(os.path.join(output_dir, "state_log.csv"), copilot_system.state_log)
    write_commands_log(os.path.join(output_dir, "commands_log.csv"), copilot_system.commands_log)
    write_feature_decision_log(os.path.join(output_dir, "feature_decision.csv"), copilot_system.feature_decision_log)

    print(f"
Output logs written to '{output_dir}'.")

if __name__ == "__main__":
    main()
