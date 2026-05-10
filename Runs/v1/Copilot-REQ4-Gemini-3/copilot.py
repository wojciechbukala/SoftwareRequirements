import argparse
import csv
import os
from enum import Enum

# --- Enumerated domains ---
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

# --- Threshold constants ---
LIDAR_DANGER = 5
OVERRIDE_FORCE = 10
VALID_RESPONSE_FORCE = 3
PROMPT_INTERVAL = 120
RESPONSE_WINDOW = 5

# --- Data Structures for Logging ---
class StateLogEntry:
    def __init__(self, time, previous, current, trigger_event=""):
        self.time = time
        self.previous = previous
        self.current = current
        self.trigger_event = trigger_event # Not in alloy model, but in requirements output

    def to_csv_row(self):
        return [self.time, self.previous.value, self.current.value, self.trigger_event]

class Command:
    def __init__(self, time, target):
        self.time = time
        self.target = target

    def to_csv_row(self):
        return [self.time, self.target.value]

class FeatureDecision:
    def __init__(self, time, feature, value):
        self.time = time
        self.feature = feature
        self.value = value

    def to_csv_row(self):
        return [self.time, self.feature.value, self.value.value]

# --- Event Classes ---
class Event:
    def __init__(self, time):
        self.time = time

    def __lt__(self, other):
        return self.time < other.time

class SensorEvent(Event):
    def __init__(self, time, sensor_type, data_value, sensor_id=None, unit=None):
        super().__init__(time)
        self.sensor_type = sensor_type
        self.data_value = data_value
        self.sensor_id = sensor_id # Not used in alloy, but in requirements input
        self.unit = unit           # Not used in alloy, but in requirements input

class DriverEvent(Event):
    def __init__(self, time, event_type, force=None):
        super().__init__(time)
        self.event_type = event_type
        self.force = force

# --- SystemState ---
class SystemState:
    def __init__(self):
        self.current_state = State.DISENGAGED
        self.current_time = 0
        self.last_prompt = 0
        self.awaiting_since = 0

        self.state_log = []
        self.commands_log = []
        self.feature_decision_log = []

        self.processed_events = set() # Use a set for processed events for efficient lookup

    def _add_state_log(self, time, previous_state, current_state, trigger_event=""):
        self.state_log.append(StateLogEntry(time, previous_state, current_state, trigger_event))

    def _emit_command(self, time, actuator):
        self.commands_log.append(Command(time, actuator))

    def _emit_feature_decision(self, time, feature, decision_value):
        self.feature_decision_log.append(FeatureDecision(time, feature, decision_value))

    def _tick_time(self):
        self.current_time += 1

    def _process_event(self, event):
        self.processed_events.add(event)

    def handle_engage_driver_event(self, event):
        self._process_event(event)
        self._tick_time()

        if self.current_state == State.DISENGAGED:
            self._add_state_log(event.time, self.current_state, State.ENGAGED, event.event_type.value)
            self.current_state = State.ENGAGED
            self.last_prompt = self.current_time


    def handle_disengage_driver_event(self, event):
        self._process_event(event)
        self._tick_time()

        if self.current_state != State.DISENGAGED:
            self._add_state_log(event.time, self.current_state, State.DISENGAGED, event.event_type.value)
            self.current_state = State.DISENGAGED

    def handle_steering_force_driver_event(self, event):
        self._process_event(event)
        self._tick_time()

        force = event.force
        if force is not None:
            # Override: force > OVERRIDE_FORCE, any state -> Disengaged (FR-04)
            if force > OVERRIDE_FORCE:
                if self.current_state != State.DISENGAGED:
                    self._add_state_log(event.time, self.current_state, State.DISENGAGED, event.event_type.value)
                    self.current_state = State.DISENGAGED
            # Valid response while AwaitingResponse -> Engaged, reset prompt timer
            elif force <= VALID_RESPONSE_FORCE and self.current_state == State.AWAITING_RESPONSE:
                self._add_state_log(event.time, State.AWAITING_RESPONSE, State.ENGAGED, event.event_type.value)
                self.current_state = State.ENGAGED
                self.last_prompt = self.current_time
                self.awaiting_since = 0 # Reset awaiting since
            # Alarm escape: low force while Alarming -> Engaged, reset prompt timer
            elif force <= VALID_RESPONSE_FORCE and self.current_state == State.ALARMING:
                self._add_state_log(event.time, State.ALARMING, State.ENGAGED, event.event_type.value)
                self.current_state = State.ENGAGED
                self.last_prompt = self.current_time
                self.awaiting_since = 0 # Reset awaiting since
            # Ignored mid-range force while AwaitingResponse -> no-op, keep waiting
            elif VALID_RESPONSE_FORCE < force <= OVERRIDE_FORCE and self.current_state == State.AWAITING_RESPONSE:
                pass # No-op, state remains AwaitingResponse
            # Other cases (e.g., low force in Disengaged/Engaged) -> no-op
            else:
                pass


    def handle_lidar_sensor_event(self, event):
        self._process_event(event)
        self._tick_time()

        if event.data_value < LIDAR_DANGER:
            self._emit_feature_decision(event.time, FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.BRAKE)
            self._emit_command(event.time, Actuator.BRAKING_SYSTEM)
        else:
            self._emit_feature_decision(event.time, FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.NO_BRAKE)

    def handle_camera_sensor_event(self, event):
        self._process_event(event)
        self._tick_time()

        if self.current_state == State.ENGAGED:
            self._emit_feature_decision(event.time, FeatureDecisionKind.LANE_KEEPING, DecisionValue.ADJUST)
            self._emit_feature_decision(event.time, FeatureDecisionKind.CRUISE_CONTROL, DecisionValue.ADJUST)
            self._emit_command(event.time, Actuator.STEERING_MOTOR)
            self._emit_command(Actuator.SPEED_ACTUATOR)

    def internal_step(self):
        # No event processing, just time tick and internal state changes
        self._tick_time()

        # prompt: Engaged long enough since last prompt -> AwaitingResponse
        if self.current_state == State.ENGAGED and 
           self.current_time >= (self.last_prompt + PROMPT_INTERVAL):
            self._add_state_log(self.current_time, State.ENGAGED, State.AWAITING_RESPONSE, "PROMPT_TIMEOUT")
            self.current_state = State.AWAITING_RESPONSE
            self.awaiting_since = self.current_time
            self._emit_command(self.current_time, Actuator.STEERING_MOTOR) # Prompt driver

        # response timeout: AwaitingResponse longer than window -> Alarming
        elif self.current_state == State.AWAITING_RESPONSE and 
             self.current_time >= (self.awaiting_since + RESPONSE_WINDOW):
            self._add_state_log(self.current_time, State.AWAITING_RESPONSE, State.ALARMING, "RESPONSE_TIMEOUT")
            self.current_state = State.ALARMING
            self._emit_command(self.current_time, Actuator.ALARM_ACTUATOR)

        # alarm tick: keep Alarming, emit one alarm command per tick
        elif self.current_state == State.ALARMING:
            self._emit_command(self.current_time, Actuator.ALARM_ACTUATOR)

    def run_simulation(self, all_events):
        all_events.sort(key=lambda e: e.time)
        event_queue = all_events[:] # Create a shallow copy

        # Initialize current_time to the time of the first event if available, otherwise 0.
        # This handles cases where the first event is not at time 0.
        if event_queue:
            self.current_time = event_queue[0].time

        while True:
            # Check for termination condition
            if not event_queue and self.current_state == State.DISENGAGED and 
               not (self.current_state == State.AWAITING_RESPONSE and self.current_time >= (self.awaiting_since + RESPONSE_WINDOW)) and 
               self.current_state != State.ALARMING and 
               not (self.current_state == State.ENGAGED and self.current_time < (self.last_prompt + PROMPT_INTERVAL)): # Added for engaged state
                break

            # Process all events at the current timestamp
            events_at_current_time = [e for e in event_queue if e.time == self.current_time]
            if events_at_current_time:
                # Remove events processed in this tick from the queue
                event_queue = [e for e in event_queue if e.time != self.current_time]
                for event in events_at_current_time:
                    # Dispatch event to appropriate handler
                    if isinstance(event, SensorEvent):
                        if event.sensor_type == SensorType.LIDAR:
                            self.handle_lidar_sensor_event(event)
                        elif event.sensor_type == SensorType.CAMERA:
                            self.handle_camera_sensor_event(event)
                    elif isinstance(event, DriverEvent):
                        if event.event_type == DriverEventType.ENGAGE:
                            self.handle_engage_driver_event(event)
                        elif event.event_type == DriverEventType.DISENGAGE:
                            self.handle_disengage_driver_event(event)
                        elif event.event_type == DriverEventType.STEERING_FORCE:
                            self.handle_steering_force_driver_event(event)
            else:
                self.internal_step()

            # Time progression logic
            if event_queue:
                next_event_time = event_queue[0].time
            else:
                next_event_time = float('inf')

            # Ensure time always progresses by at least 1 unit if simulation is active
            if self.current_state == State.ALARMING:
                self.current_time += 1
            elif self.current_state == State.DISENGAGED: # If Disengaged and no events, keep time from advancing indefinitely
                pass
            elif event_queue and self.current_time < event_queue[0].time:
                 # If there are future events, advance time to the next event or just by one tick
                self.current_time = min(event_queue[0].time, self.current_time + 1)
            elif not event_queue and self.current_state == State.AWAITING_RESPONSE and 
                 self.current_time < (self.awaiting_since + RESPONSE_WINDOW):
                # If awaiting response and not timed out yet, keep ticking
                self.current_time += 1
            elif not event_queue and self.current_state == State.ENGAGED and 
                 self.current_time < (self.last_prompt + PROMPT_INTERVAL):
                # If engaged and not time for next prompt, keep ticking
                self.current_time += 1
            elif not event_queue and self.current_state != State.DISENGAGED:
                # Catch all for other active states without pending events, ensures time advances
                self.current_time += 1
            elif self.current_time >= next_event_time:
                # If current_time has somehow already passed next_event_time (e.g., due to internal_step advancing it)
                # or is equal, we don't need to force another increment here as next events will be processed.
                pass
            else: # If no specific condition matched, just advance time
                self.current_time += 1


# --- CSV Handling Functions ---
def read_sensor_log(file_path):
    events = []
    with open(file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                time = int(row['timestamp'])
                sensor_type = SensorType(row['sensor_type'])
                data_value = int(row['data_value'])
                sensor_id = row.get('sensor_id') # Optional
                unit = row.get('unit')           # Optional
                events.append(SensorEvent(time, sensor_type, data_value, sensor_id, unit))
            except (ValueError, KeyError) as e:
                print(f"Error reading sensor_log.csv row: {row} - {e}")
    return events

def read_driver_events(file_path):
    events = []
    with open(file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                time = int(row['timestamp'])
                event_type = DriverEventType(row['event_type'])
                # The 'value' column in driver_events.csv corresponds to 'force' in DriverEvent
                force = int(row['value']) if row.get('value') else None
                events.append(DriverEvent(time, event_type, force))
            except (ValueError, KeyError) as e:
                print(f"Error reading driver_events.csv row: {row} - {e}")
    return events

def write_state_log(file_path, log_entries):
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['timestamp', 'previous_state', 'current_state', 'trigger_event'])
        for entry in log_entries:
            writer.writerow(entry.to_csv_row())

def write_commands_log(file_path, log_entries):
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['timestamp', 'actuator_id'])
        for entry in log_entries:
            writer.writerow(entry.to_csv_row())

def write_feature_decision_log(file_path, log_entries):
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['timestamp', 'feature', 'decision'])
        for entry in log_entries:
            writer.writerow(entry.to_csv_row())

# --- Main CLI Logic ---
def main():
    parser = argparse.ArgumentParser(description="Copilot - Advanced Driver Assistance System Simulator")
    parser.add_argument("--input", required=True, help="Path to the input directory containing sensor_log.csv and driver_events.csv")
    parser.add_argument("--output", required=True, help="Path to the output directory for state_log.csv, commands_log.csv, and feature_decision.csv")
    args = parser.parse_args()

    print(f"Copilot Simulation Started. Input: {args.input}, Output: {args.output}")

    input_dir = args.input
    output_dir = args.output

    # Read input files
    sensor_events = read_sensor_log(os.path.join(input_dir, 'sensor_log.csv'))
    driver_events = read_driver_events(os.path.join(input_dir, 'driver_events.csv'))

    all_events = sensor_events + driver_events

    system = SystemState()
    system.run_simulation(all_events)

    # Write output files
    os.makedirs(output_dir, exist_ok=True)
    write_state_log(os.path.join(output_dir, 'state_log.csv'), system.state_log)
    write_commands_log(os.path.join(output_dir, 'commands_log.csv'), system.commands_log)
    write_feature_decision_log(os.path.join(output_dir, 'feature_decision.csv'), system.feature_decision_log)

    print("Copilot Simulation Finished.")

if __name__ == "__main__":
    main()