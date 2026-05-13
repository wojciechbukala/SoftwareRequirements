import csv
import argparse
from datetime import datetime, timedelta
import os
from enum import Enum

# --- Constants ---
EMERGENCY_BRAKING_DISTANCE = 5.0  # meters
ATTENTIVENESS_PROMPT_INTERVAL = timedelta(seconds=120)
ATTENTIVENESS_RESPONSE_WINDOW = timedelta(seconds=5)
VALID_ATTENTIVENESS_RESPONSE_FORCE = 3.0  # N
IGNORED_STEERING_FORCE_MIN = 3.0  # N (exclusive)
IGNORED_STEERING_FORCE_MAX = 10.0  # N (exclusive)
DRIVER_OVERRIDE_FORCE = 10.0  # N (exclusive)
PROCESSING_LATENCY_LIMIT = timedelta(milliseconds=50) # Not directly used in simulation logic, but good to keep in mind for performance

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

class FeatureType(Enum):
    EMERGENCY_BRAKING = "EmergencyBraking"
    LANE_KEEPING = "LaneKeeping"
    CRUISE_CONTROL = "CruiseControl"

class ActuatorId(Enum):
    BRAKING_SYSTEM = "BrakingSystem"
    STEERING_MOTOR = "SteeringMotor"
    SPEED_ACTUATOR = "SpeedActuator"
    ALARM = "Alarm"

# --- Data Structures for Events and Logs ---
class Event:
    def __init__(self, timestamp: datetime):
        self.timestamp = timestamp

    def __lt__(self, other):
        return self.timestamp < other.timestamp

class SensorEvent(Event):
    def __init__(self, timestamp: datetime, sensor_id: str, sensor_type: SensorType, data_value: float, unit: str):
        super().__init__(timestamp)
        self.sensor_id = sensor_id
        self.sensor_type = sensor_type
        self.data_value = data_value
        self.unit = unit

    def __repr__(self):
        return f"SensorEvent({self.timestamp}, {self.sensor_id}, {self.sensor_type.value}, {self.data_value}{self.unit})"

class DriverEvent(Event):
    def __init__(self, timestamp: datetime, event_type: DriverEventType, value: float = None):
        super().__init__(timestamp)
        self.event_type = event_type
        self.value = value

    def __repr__(self):
        return f"DriverEvent({self.timestamp}, {self.event_type.value}, {self.value})"

class StateLog:
    HEADER = ["timestamp", "previous_state", "current_state", "trigger_event"]

    def __init__(self, timestamp: datetime, previous_state: CopilotState, current_state: CopilotState, trigger_event: str):
        self.timestamp = timestamp
        self.previous_state = previous_state
        self.current_state = current_state
        self.trigger_event = trigger_event

    def to_list(self):
        return [self.timestamp.isoformat(timespec='milliseconds'), self.previous_state.value, self.current_state.value, self.trigger_event]

class CommandLog:
    HEADER = ["timestamp", "actuator_id", "values"]

    def __init__(self, timestamp: datetime, actuator_id: ActuatorId, values: float):
        self.timestamp = timestamp
        self.actuator_id = actuator_id
        self.values = values

    def to_list(self):
        return [self.timestamp.isoformat(timespec='milliseconds'), self.actuator_id.value, self.values]

class FeatureDecisionLog:
    HEADER = ["timestamp", "feature", "decision"]

    def __init__(self, timestamp: datetime, feature: FeatureType, decision: str):
        self.timestamp = timestamp
        self.feature = feature
        self.decision = decision

    def to_list(self):
        return [self.timestamp.isoformat(timespec='milliseconds'), self.feature.value, self.decision]

# --- CSV Parsing Utilities ---
def parse_timestamp(ts_str: str) -> datetime:
    return datetime.fromisoformat(ts_str.replace('Z', '+00:00')) # Handle 'Z' for UTC

def read_sensor_events(file_path: str) -> list[SensorEvent]:
    events = []
    with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                timestamp = parse_timestamp(row["timestamp"])
                sensor_id = row["sensor_id"]
                sensor_type = SensorType(row["sensor_type"])
                data_value = float(row["data_value"])
                unit = row["unit"]
                events.append(SensorEvent(timestamp, sensor_id, sensor_type, data_value, unit))
            except (ValueError, KeyError) as e:
                print(f"Skipping malformed sensor event row: {row} - {e}")
    return events

def read_driver_events(file_path: str) -> list[DriverEvent]:
    events = []
    with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                timestamp = parse_timestamp(row["timestamp"])
                event_type = DriverEventType(row["event_type"])
                value = float(row["value"]) if row.get("value") else None
                events.append(DriverEvent(timestamp, event_type, value))
            except (ValueError, KeyError) as e:
                print(f"Skipping malformed driver event row: {row} - {e}")
    return events

# --- Main Copilot System ---
class Copilot:
    def __init__(self):
        self.state = CopilotState.DISENGAGED
        self.state_logs: list[StateLog] = []
        self.command_logs: list[CommandLog] = []
        self.feature_decision_logs: list[FeatureDecisionLog] = []
        self.last_attentiveness_prompt_time: datetime = None
        self.awaiting_response_start_time: datetime = None
        self.last_event_timestamp: datetime = None

    def _transition_state(self, new_state: CopilotState, timestamp: datetime, trigger_event: str):
        if self.state != new_state:
            self.state_logs.append(StateLog(timestamp, self.state, new_state, trigger_event))
            print(f"[{timestamp.isoformat(timespec='milliseconds')}] STATE: {self.state.value} -> {new_state.value} ({trigger_event})")
            self.state = new_state

    def process_event(self, event: Event):
        self.last_event_timestamp = event.timestamp
        current_timestamp = event.timestamp

        # Check for attentiveness prompt timeout if AWAITING_RESPONSE
        if self.state == CopilotState.AWAITING_RESPONSE and current_timestamp >= (self.awaiting_response_start_time + ATTENTIVENESS_RESPONSE_WINDOW):
            print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] Attentiveness response timed out.")
            self._transition_state(CopilotState.ALARMING, current_timestamp, "AttentivenessTimeout")
            self.command_logs.append(CommandLog(current_timestamp, ActuatorId.ALARM, 1.0)) # Emit continuous alarm

        # Attentiveness prompt interval check if ENGAGED
        if self.state == CopilotState.ENGAGED:
            if self.last_attentiveness_prompt_time is None or 
               current_timestamp >= (self.last_attentiveness_prompt_time + ATTENTIVENESS_PROMPT_INTERVAL):
                print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] Issuing attentiveness prompt.")
                self.command_logs.append(CommandLog(current_timestamp, ActuatorId.STEERING_MOTOR, 0.1)) # Small steering movement
                self._transition_state(CopilotState.AWAITING_RESPONSE, current_timestamp, "AttentivenessPrompt")
                self.awaiting_response_start_time = current_timestamp
                self.last_attentiveness_prompt_time = current_timestamp # Reset for next prompt cycle

        # Process SensorEvent
        if isinstance(event, SensorEvent):
            self._handle_sensor_event(event)
        # Process DriverEvent
        elif isinstance(event, DriverEvent):
            self._handle_driver_event(event)

    def _handle_sensor_event(self, event: SensorEvent):
        current_timestamp = event.timestamp
        
        # Always log sensor event data, regardless of state
        # FR-02: When in Disengaged mode, data shall be logged but without further actions on actuator commands or feature decisions.
        # PF-01: Every sensor event is first recorded by the program as received.
        # We model "recorded as received" as logging decisions for relevant sensors, even if no action is taken.

        is_emergency_braking_triggered = False

        # PF-01: If the event originates from a Lidar sensor... evaluates emergency braking before considering any other feature
        if event.sensor_type == SensorType.LIDAR:
            if event.data_value < EMERGENCY_BRAKING_DISTANCE:
                decision = f"Obstacle detected at {event.data_value}{event.unit}, initiating emergency braking."
                self.feature_decision_logs.append(FeatureDecisionLog(current_timestamp, FeatureType.EMERGENCY_BRAKING, decision))
                print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] {FeatureType.EMERGENCY_BRAKING.value} Decision: {decision}")
                
                # Only issue command if not disengaged
                if self.state != CopilotState.DISENGAGED:
                    self.command_logs.append(CommandLog(current_timestamp, ActuatorId.BRAKING_SYSTEM, 1.0)) # Full brake
                    print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] Command: {ActuatorId.BRAKING_SYSTEM.value} (1.0)")
                is_emergency_braking_triggered = True
            else:
                decision = f"No obstacle within {EMERGENCY_BRAKING_DISTANCE}{event.unit} ({event.data_value}{event.unit})"
                self.feature_decision_logs.append(FeatureDecisionLog(current_timestamp, FeatureType.EMERGENCY_BRAKING, decision))
                print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] {FeatureType.EMERGENCY_BRAKING.value} Decision: {decision}")

        # FR-02: When emergency braking is triggered, Copilot ... should abandon processing lane keeping or cruise control for that cycle.
        if is_emergency_braking_triggered:
            return

        # PF-01: If the event originates from a sensor other than Lidar, the program only takes further action when it is currently in engaged mode.
        if self.state == CopilotState.ENGAGED:
            if event.sensor_type == SensorType.CAMERA:
                # FR-02: For camera sensor readings, a lane keeping correction value and cruise control adjustment shall be computed and provided to the actuator.
                # Assuming data_value represents some combined input for both.
                # For simulation, we'll use simple placeholder logic for values.
                lane_keeping_correction = event.data_value * 0.01 # Placeholder logic
                cruise_control_adjustment = event.data_value * 0.005 # Placeholder logic

                decision_lk = f"Lane keeping correction computed: {lane_keeping_correction}"
                self.feature_decision_logs.append(FeatureDecisionLog(current_timestamp, FeatureType.LANE_KEEPING, decision_lk))
                self.command_logs.append(CommandLog(current_timestamp, ActuatorId.STEERING_MOTOR, lane_keeping_correction))
                print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] {FeatureType.LANE_KEEPING.value} Decision: {decision_lk}")
                print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] Command: {ActuatorId.STEERING_MOTOR.value} ({lane_keeping_correction})")


                decision_cc = f"Cruise control adjustment computed: {cruise_control_adjustment}"
                self.feature_decision_logs.append(FeatureDecisionLog(current_timestamp, FeatureType.CRUISE_CONTROL, decision_cc))
                self.command_logs.append(CommandLog(current_timestamp, ActuatorId.SPEED_ACTUATOR, cruise_control_adjustment))
                print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] {FeatureType.CRUISE_CONTROL.value} Decision: {decision_cc}")
                print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] Command: {ActuatorId.SPEED_ACTUATOR.value} ({cruise_control_adjustment})")

        elif self.state == CopilotState.DISENGAGED:
            # FR-02: When in Disengaged mode, data shall be logged but without further actions on actuator commands or feature decisions.
            # We already log decision for emergency braking. For other sensors, just note that no action was taken.
            if event.sensor_type == SensorType.CAMERA:
                self.feature_decision_logs.append(FeatureDecisionLog(current_timestamp, FeatureType.LANE_KEEPING, "Disengaged: No action"))
                self.feature_decision_logs.append(FeatureDecisionLog(current_timestamp, FeatureType.CRUISE_CONTROL, "Disengaged: No action"))
                print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] Disengaged: Camera sensor event received, but no actions taken.")


    def _handle_driver_event(self, event: DriverEvent):
        current_timestamp = event.timestamp

        # FR-04: Driver Override (Highest priority for driver events)
        if event.event_type == DriverEventType.STEERING_FORCE and event.value > DRIVER_OVERRIDE_FORCE:
            print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] Driver override detected (force: {event.value}N).")
            self._transition_state(CopilotState.DISENGAGED, current_timestamp, "DriverOverride")
            # Reset attentiveness monitoring if override occurs
            self.last_attentiveness_prompt_time = None
            self.awaiting_response_start_time = None
            return # Driver override takes precedence, no other driver event logic for this cycle

        if event.event_type == DriverEventType.ENGAGE:
            if self.state == CopilotState.DISENGAGED:
                self._transition_state(CopilotState.ENGAGED, current_timestamp, event.event_type.value)
                self.last_attentiveness_prompt_time = current_timestamp # Start attentiveness timer
            elif self.state != CopilotState.ENGAGED:
                print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] Attempted ENGAGE from {self.state.value}, ignored.")

        elif event.event_type == DriverEventType.DISENGAGE:
            if self.state != CopilotState.DISENGAGED:
                self._transition_state(CopilotState.DISENGAGED, current_timestamp, event.event_type.value)
                # Reset attentiveness monitoring
                self.last_attentiveness_prompt_time = None
                self.awaiting_response_start_time = None
            elif self.state == CopilotState.DISENGAGED:
                print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] Attempted DISENGAGE from {self.state.value}, ignored.")

        elif event.event_type == DriverEventType.STEERING_FORCE:
            force_value = event.value
            if self.state == CopilotState.AWAITING_RESPONSE:
                # FR-03: A valid response is assumed to be wheel force of 3N or less within the 5-second window.
                if force_value <= VALID_ATTENTIVENESS_RESPONSE_FORCE:
                    print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] Valid attentiveness response received ({force_value}N).")
                    self._transition_state(CopilotState.ENGAGED, current_timestamp, "ValidAttentivenessResponse")
                    self.awaiting_response_start_time = None # Clear awaiting response timer
                    self.last_attentiveness_prompt_time = current_timestamp # Reset prompt timer
                # FR-03: A steering wheel force event with a value strictly greater than 3N and strictly less than 10N shall be ignored
                elif IGNORED_STEERING_FORCE_MIN < force_value < IGNORED_STEERING_FORCE_MAX:
                    print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] Ignoring steering force ({force_value}N) during AWAITING_RESPONSE.")
                # Forces outside these ranges (e.g., negative, very large but not override, or exactly 10N) are not explicitly handled by FR-03
                # For this simulation, we'll implicitly ignore them if they don't meet other criteria.

            elif self.state == CopilotState.ALARMING:
                # FR-03: The system escapes the Alarming state na transitions to Engaged state if a steering wheel force event with a value of 3N or less is received.
                if force_value <= VALID_ATTENTIVENESS_RESPONSE_FORCE:
                    print(f"[{current_timestamp.isoformat(timespec='milliseconds')}] Alarm cancelled by driver response ({force_value}N).")
                    self._transition_state(CopilotState.ENGAGED, current_timestamp, "AlarmCancelled")
                    self.command_logs.append(CommandLog(current_timestamp, ActuatorId.ALARM, 0.0)) # Turn off alarm
                    self.last_attentiveness_prompt_time = current_timestamp # Reset prompt timer

# --- Output Writing Utilities ---
def write_logs_to_csv(file_path: str, header: list[str], logs: list):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        for log_entry in logs:
            writer.writerow(log_entry.to_list())
    print(f"Logs written to {file_path}")

# --- Main execution ---
def main():
    parser = argparse.ArgumentParser(description="Copilot Driver-Assistance System Simulation")
    parser.add_argument("--input", required=True, help="Path to the input directory containing sensor_log.csv and driver_events.csv")
    parser.add_argument("--output", required=True, help="Path to the output directory for state_log.csv, commands_log.csv, and feature_decision_log.csv")
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    sensor_log_path = os.path.join(input_dir, "sensor_log.csv")
    driver_events_path = os.path.join(input_dir, "driver_events.csv")

    print(f"Reading sensor events from: {sensor_log_path}")
    sensor_events = read_sensor_events(sensor_log_path)
    print(f"Found {len(sensor_events)} sensor events.")

    print(f"Reading driver events from: {driver_events_path}")
    driver_events = read_driver_events(driver_events_path)
    print(f"Found {len(driver_events)} driver events.")

    # Merge and sort all events by timestamp
    all_events = sorted(sensor_events + driver_events)
    print(f"Total {len(all_events)} events merged and sorted.")

    copilot = Copilot()

    print("
Starting Copilot simulation...")
    for event in all_events:
        copilot.process_event(event)
    print("Simulation finished.
")

    # Flush logs to output files
    write_logs_to_csv(os.path.join(output_dir, "state_log.csv"), StateLog.HEADER, copilot.state_logs)
    write_logs_to_csv(os.path.join(output_dir, "commands_log.csv"), CommandLog.HEADER, copilot.command_logs)
    write_logs_to_csv(os.path.join(output_dir, "feature_decision.csv"), FeatureDecisionLog.HEADER, copilot.feature_decision_logs)

if __name__ == "__main__":
    main()
