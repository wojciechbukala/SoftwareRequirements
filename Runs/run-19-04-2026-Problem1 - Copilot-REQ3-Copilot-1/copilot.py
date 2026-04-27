import argparse
import csv
import os
import time
from enum import Enum, auto
from collections import deque

# --- Constants and Configuration ---
INPUT_DIR_DEFAULT = "."
OUTPUT_DIR_DEFAULT = "."
SENSOR_LOG_FILENAME = "sensor_log.csv"
DRIVER_EVENTS_FILENAME = "driver_events.csv"
STATE_LOG_FILENAME = "state_log.csv"
COMMANDS_LOG_FILENAME = "commands_log.csv"
FEATURE_DECISION_FILENAME = "feature_decision.csv"

# Sensor and Actuator IDs (example values)
LIDAR_SENSOR_ID = "lidar_front"
CAMERA_SENSOR_ID = "camera_front"
BRAKING_SYSTEM_ACTUATOR_ID = "braking_system"
STEERING_MOTOR_ACTUATOR_ID = "steering_motor"
SPEED_ACTUATOR_ID = "speed_actuator"
ALARM_ACTUATOR_ID = "alarm_actuator"

# Feature Names
FEATURE_EMERGENCY_BRAKING = "emergency_braking"
FEATURE_LANE_KEEPING = "lane_keeping"
FEATURE_CRUISE_CONTROL = "cruise_control"

# Lidar distance threshold for emergency braking
EMERGENCY_BRAKING_DISTANCE_THRESHOLD_M = 5.0

# Attentiveness prompt settings
ATTENTIVENESS_PROMPT_INTERVAL_S = 120
ATTENTIVENESS_RESPONSE_DEADLINE_S = 5
ATTENTIVENESS_PROMPT_FORCE_N = 3.0 # Small steering wheel movement command value

# Driver override settings
STEERING_FORCE_OVERRIDE_THRESHOLD_N = 10.0

# State Machine Definitions
class SystemState(Enum):
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    WAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"

# --- Event Definitions ---
class EventType(Enum):
    SENSOR = "sensor"
    DRIVER = "driver"

class SensorType(Enum):
    LIDAR = "Lidar"
    CAMERA = "Camera"

class DriverEventType(Enum):
    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"

# --- CSV Headers ---
SENSOR_LOG_HEADER = ["timestamp", "sensor_id", "sensor_type", "data_value", "unit"]
DRIVER_EVENTS_HEADER = ["timestamp", "event_type", "value"]
STATE_LOG_HEADER = ["timestamp", "previous_state", "current_state", "trigger_event"]
COMMANDS_LOG_HEADER = ["timestamp", "actuator_id", "values"]
FEATURE_DECISION_HEADER = ["timestamp", "feature", "decision"]

# --- Helper Classes ---

class Event:
    def __init__(self, timestamp, event_type, data):
        self.timestamp = timestamp
        self.event_type = event_type
        self.data = data # This will be a dictionary or specific object based on type

    def __lt__(self, other):
        # For sorting events by timestamp
        return self.timestamp < other.timestamp

class SensorEventData:
    def __init__(self, sensor_id, sensor_type, data_value, unit):
        self.sensor_id = sensor_id
        self.sensor_type = SensorType(sensor_type)
        self.data_value = float(data_value)
        self.unit = unit

class DriverEventData:
    def __init__(self, event_type, value):
        self.event_type = DriverEventType(event_type)
        self.value = float(value) if event_type in [DriverEventType.STEERING_FORCE.value] else value

class ActuatorCommand:
    def __init__(self, timestamp, actuator_id, values):
        self.timestamp = timestamp
        self.actuator_id = actuator_id
        self.values = values # Can be a single value or a list/dict

class FeatureDecision:
    def __init__(self, timestamp, feature, decision):
        self.timestamp = timestamp
        self.feature = feature
        self.decision = decision

class StateTransition:
    def __init__(self, timestamp, previous_state, current_state, trigger_event):
        self.timestamp = timestamp
        self.previous_state = previous_state
        self.current_state = current_state
        self.trigger_event = trigger_event # A string describing the event that caused the transition

# --- Copilot System ---

class CopilotSystem:
    def __init__(self, input_dir, output_dir):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.current_state = SystemState.DISENGAGED
        self.last_state_transition_time = time.time()
        self.last_attentiveness_prompt_time = 0
        self.awaiting_response_deadline = 0
        self.last_feature_decision_time = 0
        self.last_command_issue_time = 0

        self.output_handlers = {}
        self._setup_output_handlers()

        self.event_stream = deque()
        self.load_events()

        self.state_log_writer = None
        self.commands_log_writer = None
        self.feature_decision_writer = None
        self._setup_loggers()

        self.is_running = True

    def _setup_output_handlers(self):
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        # Setup file handlers for logs
        state_log_path = os.path.join(self.output_dir, STATE_LOG_FILENAME)
        commands_log_path = os.path.join(self.output_dir, COMMANDS_LOG_FILENAME)
        feature_decision_path = os.path.join(self.output_dir, FEATURE_DECISION_FILENAME)

        self.state_log_file = open(state_log_path, 'w', newline='', encoding='utf-8')
        self.state_log_writer = csv.writer(self.state_log_file)
        self.state_log_writer.writerow(STATE_LOG_HEADER)

        self.commands_log_file = open(commands_log_path, 'w', newline='', encoding='utf-8')
        self.commands_log_writer = csv.writer(self.commands_log_file)
        self.commands_log_writer.writerow(COMMANDS_LOG_HEADER)

        self.feature_decision_file = open(feature_decision_path, 'w', newline='', encoding='utf-8')
        self.feature_decision_writer = csv.writer(self.feature_decision_file)
        self.feature_decision_writer.writerow(FEATURE_DECISION_HEADER)

    def _setup_loggers(self):
        # This method is kept for clarity, _setup_output_handlers now handles the actual file opening and writing setup.
        # In a more complex scenario, this might involve setting up logging configurations.
        pass # No specific logger setup needed beyond CSV writers for now.


    def load_events(self):
        all_events = []

        # Load sensor events
        sensor_log_path = os.path.join(self.input_dir, SENSOR_LOG_FILENAME)
        if os.path.exists(sensor_log_path):
            with open(sensor_log_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        sensor_data = SensorEventData(
                            row['sensor_id'],
                            row['sensor_type'],
                            row['data_value'],
                            row['unit']
                        )
                        event = Event(float(row['timestamp']), EventType.SENSOR, sensor_data)
                        all_events.append(event)
                    except Exception as e:
                        print(f"Error parsing sensor event: {row} - {e}") # Basic error handling
        else:
            print(f"Warning: Sensor log file not found at {sensor_log_path}")

        # Load driver events
        driver_events_path = os.path.join(self.input_dir, DRIVER_EVENTS_FILENAME)
        if os.path.exists(driver_events_path):
            with open(driver_events_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        driver_data = DriverEventData(
                            row['event_type'],
                            row['value']
                        )
                        event = Event(float(row['timestamp']), EventType.DRIVER, driver_data)
                        all_events.append(event)
                    except Exception as e:
                        print(f"Error parsing driver event: {row} - {e}") # Basic error handling
        else:
            print(f"Warning: Driver events file not found at {driver_events_path}")

        # Sort all events by timestamp
        all_events.sort()
        self.event_stream.extend(all_events)

    def log_state_transition(self, previous_state, current_state, trigger_event):
        if previous_state != current_state:
            timestamp = time.time() # Using current time for logs, as per requirements interpretation. Could also use event timestamp.
            self.state_log_writer.writerow([
                timestamp,
                previous_state.value,
                current_state.value,
                trigger_event
            ])
            self.state_log_file.flush()
            self.last_state_transition_time = timestamp
            print(f"State transition: {previous_state.value} -> {current_state.value} (Trigger: {trigger_event})")

    def log_actuator_command(self, actuator_id, values):
        timestamp = time.time()
        self.commands_log_writer.writerow([
            timestamp,
            actuator_id,
            values
        ])
        self.commands_log_file.flush()
        self.last_command_issue_time = timestamp
        print(f"Command issued: {actuator_id} with values {values}")

    def log_feature_decision(self, feature, decision):
        timestamp = time.time()
        self.feature_decision_writer.writerow([
            timestamp,
            feature,
            decision
        ])
        self.feature_decision_file.flush()
        self.last_feature_decision_time = timestamp
        print(f"Feature decision: {feature} -> {decision}")

    def _transition_state(self, new_state, trigger_event):
        if self.current_state != new_state:
            self.log_state_transition(self.current_state, new_state, trigger_event)
            self.current_state = new_state
            # Reset timers/deadlines upon state change if applicable
            if self.current_state == SystemState.ENGAGED:
                self.last_attentiveness_prompt_time = time.time() # Reset prompt timer
                self.awaiting_response_deadline = 0 # Clear any previous deadline
            elif self.current_state == SystemState.WAITING_RESPONSE:
                self.awaiting_response_deadline = time.time() + ATTENTIVENESS_RESPONSE_DEADLINE_S
            # Added: Reset prompt timer when disengaging to avoid immediate re-prompt upon re-engagement.
            elif self.current_state == SystemState.DISENGAGED:
                self.last_attentiveness_prompt_time = 0 
                self.awaiting_response_deadline = 0

    def process_event(self, event):
        current_time = time.time() # Use real time for processing loop timing
        
        # --- Global Checks (apply regardless of state) ---
        
        # Check for driver override (STEERING_FORCE > 10N)
        if event.event_type == EventType.DRIVER and event.data.event_type == DriverEventType.STEERING_FORCE:
            if event.data.value > STEERING_FORCE_OVERRIDE_THRESHOLD_N:
                self._transition_state(SystemState.DISENGAGED, "STEERING_FORCE_OVERRIDE")
                print(f"[{current_time:.2f}] Driver override detected (Force: {event.data.value}N). Transitioning to Disengaged.")
                return # Driver override takes precedence

        # Emergency braking evaluation (PF-01) - done for ALL events, regardless of state
        emergency_braking_decision = "NO_BRAKE"
        if event.event_type == EventType.SENSOR and event.data.sensor_type == SensorType.LIDAR:
            if event.data.data_value < EMERGENCY_BRAKING_DISTANCE_THRESHOLD_M:
                emergency_braking_decision = "BRAKE"
                self.log_feature_decision(FEATURE_EMERGENCY_BRAKING, "BRAKE")
                self.log_actuator_command(BRAKING_SYSTEM_ACTUATOR_ID, "BRAKE")
                # If emergency braking is triggered, abandon other processing for this cycle
                if self.current_state != SystemState.ALARMING: # Don't abandon if already alarming
                    print(f"[{current_time:.2f}] Emergency braking triggered (Lidar: {event.data.data_value}m).")
                    return # Stop processing this event further

        # --- State-Specific Processing ---
        if self.current_state == SystemState.DISENGAGED:
            # Log data but no actions
            if event.event_type == EventType.SENSOR:
                self.log_feature_decision(FEATURE_EMERGENCY_BRAKING, emergency_braking_decision) # Log even if no-brake
            # If the event is a driver engage event, it should transition to engaged.
            if event.event_type == EventType.DRIVER and event.data.event_type == DriverEventType.ENGAGE:
                self._transition_state(SystemState.ENGAGED, "DRIVER_ENGAGE")
                print(f"[{current_time:.2f}] Driver ENGAGE event detected. Transitioning to Engaged.")
            elif event.event_type == EventType.DRIVER and event.data.event_type == DriverEventType.DISENGAGE:
                # Already disengaged, ignore or log as info
                print(f"[{current_time:.2f}] Driver DISENGAGE event received in Disengaged state. Ignored.")
            
        elif self.current_state == SystemState.ENGAGED:
            # Log raw sensor event (as per PF-01 'log raw event')
            if event.event_type == EventType.SENSOR:
                self.log_feature_decision(FEATURE_EMERGENCY_BRAKING, emergency_braking_decision) # Log if no-brake
            
            # Handle driver events
            if event.event_type == EventType.DRIVER:
                if event.data.event_type == DriverEventType.ENGAGE:
                    # Already engaged, ignore or log as info
                    print(f"[{current_time:.2f}] Driver ENGAGE event received in Engaged state. Ignored.")
                elif event.data.event_type == DriverEventType.DISENGAGE:
                    self._transition_state(SystemState.DISENGAGED, "DRIVER_DISENGAGE")
                    print(f"[{current_time:.2f}] Driver DISENGAGE event received. Transitioning to Disengaged.")
                # STEERING_FORCE is handled by global override check at the start of process_event.
            
            # Handle sensor events (Camera processing)
            elif event.event_type == EventType.SENSOR and event.data.sensor_type == SensorType.CAMERA:
                # PF-01 logic for Camera
                # Placeholder logic for corrections/adjustments
                lane_keeping_correction = f"CORRECT_{event.data.data_value:.2f}" 
                cruise_control_adjustment = f"ADJUST_{event.data.data_value:.2f}"
                
                self.log_feature_decision(FEATURE_LANE_KEEPING, lane_keeping_correction)
                self.log_feature_decision(FEATURE_CRUISE_CONTROL, cruise_control_adjustment)
                
                self.log_actuator_command(STEERING_MOTOR_ACTUATOR_ID, lane_keeping_correction)
                self.log_actuator_command(SPEED_ACTUATOR_ID, cruise_control_adjustment)
                print(f"[{current_time:.2f}] Camera event processed for Lane Keeping and Cruise Control.")
            
            # Attentiveness check (FR-03)
            if current_time - self.last_attentiveness_prompt_time >= ATTENTIVENESS_PROMPT_INTERVAL_S:
                self._transition_state(SystemState.WAITING_RESPONSE, "ATTENTIVENESS_PROMPT")
                self.log_actuator_command(STEERING_MOTOR_ACTUATOR_ID, ATTENTIVENESS_PROMPT_FORCE_N)
                print(f"[{current_time:.2f}] Issuing attentiveness prompt. Next prompt in {ATTENTIVENESS_PROMPT_INTERVAL_S}s.")

        elif self.current_state == SystemState.WAITING_RESPONSE:
            # Process driver events for response
            if event.event_type == EventType.DRIVER:
                if event.data.event_type == DriverEventType.STEERING_FORCE:
                    if event.data.value <= ATTENTIVENESS_PROMPT_FORCE_N: # Valid response
                        self._transition_state(SystemState.ENGAGED, "VALID_RESPONSE")
                        print(f"[{current_time:.2f}] Valid steering force detected (Force: {event.data.value}N). Returning to Engaged state.")
                    # STEERING_FORCE > ATTENTIVENESS_PROMPT_FORCE_N but <= STEERING_FORCE_OVERRIDE_THRESHOLD_N
                    # This is ignored as per state machine (3N < steering force < 10N [ignored])
                elif event.data.event_type == DriverEventType.DISENGAGE:
                    self._transition_state(SystemState.DISENGAGED, "DRIVER_DISENGAGE_DURING_WAITING")
                    print(f"[{current_time:.2f}] Driver DISENGAGE event received during waiting. Transitioning to Disengaged.")
            
            # Check deadline for response (FR-03)
            if current_time > self.awaiting_response_deadline:
                self._transition_state(SystemState.ALARMING, "NO_VALID_RESPONSE")
                print(f"[{current_time:.2f}] Attentiveness response deadline missed. Transitioning to Alarming.")

        elif self.current_state == SystemState.ALARMING:
            # Continuously issue alarm commands (FR-03)
            self.log_actuator_command(ALARM_ACTUATOR_ID, "ALARM")

            # Handle driver events to exit alarming state
            if event.event_type == EventType.DRIVER:
                if event.data.event_type == DriverEventType.STEERING_FORCE:
                    if event.data.value <= ATTENTIVENESS_PROMPT_FORCE_N: # Valid response to stop alarm
                        self._transition_state(SystemState.ENGAGED, "VALID_RESPONSE_TO_ALARM")
                        print(f"[{current_time:.2f}] Valid steering force detected (Force: {event.data.value}N). Exiting Alarming, returning to Engaged.")
                    elif event.data.value > STEERING_FORCE_OVERRIDE_THRESHOLD_N: # Driver override during alarming
                        self._transition_state(SystemState.DISENGAGED, "STEERING_FORCE_OVERRIDE_DURING_ALARMING")
                        print(f"[{current_time:.2f}] Driver override detected during alarming. Transitioning to Disengaged.")
                elif event.data.event_type == DriverEventType.DISENGAGE:
                    self._transition_state(SystemState.DISENGAGED, "DRIVER_DISENGAGE_DURING_ALARMING")
                    print(f"[{current_time:.2f}] Driver DISENGAGE event received during alarming. Transitioning to Disengaged.")
            
            # If car turned off (not explicitly modeled, but implied by program termination)
            # The program termination logic will handle this.

    def run(self):
        print("Copilot system starting...")
        self._transition_state(SystemState.DISENGAGED, "PROGRAM_START")
        # Initialize prompt timer on startup to avoid immediate prompt if events start at 0s
        self.last_attentiveness_prompt_time = time.time() 

        while self.event_stream and self.is_running:
            event = self.event_stream.popleft()
            
            # Check for program termination condition (e.g., car turned off) - simplified for now
            # In a real scenario, this might be an event or a signal.
            # For this simulation, we can assume it stops after processing all events.
            
            # Simulate processing time delay to check performance targets (optional, for dev/debug)
            # event_processing_start_time = time.time()

            self.process_event(event)

            # event_processing_end_time = time.time()
            # processing_time = event_processing_end_time - event_processing_start_time
            # if processing_time > 0.050: # 50 ms threshold
            #     print(f"Performance Warning: Event processing took {processing_time:.4f}s, exceeding 50ms.")
            
            # Check for car turned off state transition (not explicitly defined in events, but in diagram)
            # This is a placeholder for termination logic. In a real system, there would be an explicit signal.
            # For simulation, we might exit after all events are processed or if a specific "OFF" event occurs.
            # For now, assume it runs until event_stream is empty.

        print("All events processed. Copilot system shutting down.")
        self.close_loggers()
 atividades:
- Parse REQUIREMENTS.md to identify core functionalities, states, event types, and output formats.
- Set up the main Python script 'copilot.py' with basic structure, including argument parsing for input and output directories.
- Implement CSV reading and merging logic to create a single chronological event stream from 'sensor_log.csv' and 'driver_events.csv'.
- Define and implement the Copilot state machine with states: Disengaged, Engaged, AwaitingResponse, Alarming.
- Implement event handlers for driver events (ENGAGE, DISENGAGE, STEERING_FORCE) to manage state transitions.
- Implement sensor event processing logic for Lidar (emergency braking) and Camera (lane keeping, cruise control).
- Integrate sensor and driver event processing with the state machine, ensuring correct state transitions and feature decision logic.
- Implement attentiveness monitoring: issuing prompts and handling responses according to the state machine rules and timing.
- Implement emergency braking logic (Lidar < 5m) with highest priority.
- Implement output logging to 'state_log.csv', 'commands_log.csv', and 'feature_decision.csv' with correct headers and data formats.
- Add inline documentation and adhere to clean code principles.
- Ensure the system can be run from the command line using 'copilot --input <dir> --output <dir>'.
- Write a summary of the implemented work to SUMMARY.md.
AGUID:a1b2c3d4-e5f6-7890-1234-567890abcdef