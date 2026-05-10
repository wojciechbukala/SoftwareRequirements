import time
from typing import List, Union

from constants import (
    SystemState, SensorType, DriverEventType, ActuatorID, Feature,
    EMERGENCY_BRAKING_DISTANCE_M, ATTENTIVENESS_PROMPT_INTERVAL_S,
    ATTENTIVENESS_RESPONSE_WINDOW_S, ATTENTIVENESS_VALID_RESPONSE_FORCE_N,
    DRIVER_OVERRIDE_FORCE_N,
)
from data_models import (
    SensorEvent, DriverEvent, StateLogEntry, CommandLogEntry, FeatureDecisionEntry
)

class Copilot:
    def __init__(self):
        self._state: SystemState = SystemState.DISENGAGED
        self._state_log: List[StateLogEntry] = []
        self._commands_log: List[CommandLogEntry] = []
        self._feature_decision_log: List[FeatureDecisionEntry] = []

        self._last_attentiveness_prompt_time: float = 0.0
        self._awaiting_response_start_time: float = 0.0
        self._last_event_timestamp: float = 0.0 # To track time progression in simulation

        print(f"Copilot initialized. Current state: {self._state.value}")
        self._log_state_change(0.0, SystemState.DISENGAGED, "System initialized")

    @property
    def state(self) -> SystemState:
        return self._state

    @property
    def state_log(self) -> List[StateLogEntry]:
        return self._state_log

    @property
    def commands_log(self) -> List[CommandLogEntry]:
        return self._commands_log

    @property
    def feature_decision_log(self) -> List[FeatureDecisionEntry]:
        return self._feature_decision_log

    def _log_state_change(self, timestamp: float, new_state: SystemState, trigger_event: str):
        if self._state != new_state:
            self._state_log.append(
                StateLogEntry(timestamp, self._state, new_state, trigger_event)
            )
            print(f"[{timestamp:.2f}s] STATE CHANGE: {self._state.value} -> {new_state.value} (Trigger: {trigger_event})")
            self._state = new_state
        # FR-01: events that keep the system in the same state shall not be recorded.

    def _log_command(self, timestamp: float, actuator_id: ActuatorID, value: Union[float, str]):
        self._commands_log.append(
            CommandLogEntry(timestamp, actuator_id, value)
        )
        print(f"[{timestamp:.2f}s] COMMAND: {actuator_id.value} -> {value}")

    def _log_feature_decision(self, timestamp: float, feature: Feature, decision: Union[float, str]):
        self._feature_decision_log.append(
            FeatureDecisionEntry(timestamp, feature, decision)
        )
        print(f"[{timestamp:.2f}s] FEATURE DECISION: {feature.value} -> {decision}")

    def _handle_emergency_braking(self, event: SensorEvent):
        """
        Handles emergency braking logic. Always active.
        """
        if event.sensor_type == SensorType.LIDAR:
            if event.data_value < EMERGENCY_BRAKING_DISTANCE_M:
                self._log_feature_decision(event.timestamp, Feature.EMERGENCY_BRAKING, "BRAKING")
                self._log_command(event.timestamp, ActuatorID.BRAKING_SYSTEM, "APPLY_BRAKE")
                return True # Emergency braking triggered
            else:
                self._log_feature_decision(event.timestamp, Feature.EMERGENCY_BRAKING, "NON_BRAKING")
        return False # Emergency braking not triggered or not a Lidar event

    def _handle_attentiveness_check(self, timestamp: float):
        """
        Manages attentiveness prompting and state transitions (FR-03).
        """
        if self._state == SystemState.ENGAGED:
            # Check if it's time to prompt for attentiveness
            if (timestamp - self._last_attentiveness_prompt_time) >= ATTENTIVENESS_PROMPT_INTERVAL_S:
                self._log_command(timestamp, ActuatorID.STEERING_MOTOR, "SMALL_MOVEMENT") # Attentiveness prompt
                self._log_state_change(timestamp, SystemState.AWAITING_RESPONSE, "Attentiveness prompt issued")
                self._awaiting_response_start_time = timestamp
                self._last_attentiveness_prompt_time = timestamp # Reset timer immediately after prompting
        
        elif self._state == SystemState.AWAITING_RESPONSE:
            # Check for timeout if no response received
            if (timestamp - self._awaiting_response_start_time) >= ATTENTIVENESS_RESPONSE_WINDOW_S:
                self._log_state_change(timestamp, SystemState.ALARMING, "Attentiveness response timeout")
                self._log_command(timestamp, ActuatorID.ALARM, "CONTINUOUS_ALARM")
        
        elif self._state == SystemState.ALARMING:
            # Continuous alarm
            self._log_command(timestamp, ActuatorID.ALARM, "CONTINUOUS_ALARM")


    def process_event(self, timestamp: float, event: Union[SensorEvent, DriverEvent]):
        self._last_event_timestamp = timestamp # Update the last known timestamp

        # PF-02: Attentiveness check needs to run on every loop iteration to monitor timers
        self._handle_attentiveness_check(timestamp)

        # FR-04: Driver Override is always highest priority for driver events
        if isinstance(event, DriverEvent) and event.event_type == DriverEventType.STEERING_FORCE:
            if event.value > DRIVER_OVERRIDE_FORCE_N:
                if self._state != SystemState.DISENGAGED:
                    self._log_state_change(timestamp, SystemState.DISENGAGED, "Driver override (force > 10N)")
                return # Override takes precedence, no further processing for this event

        # Handle sensor events (PF-01)
        if isinstance(event, SensorEvent):
            emergency_braking_triggered = self._handle_emergency_braking(event)

            if emergency_braking_triggered:
                # FR-02: abandon processing lane keeping or cruise control
                return

            if self._state == SystemState.ENGAGED:
                if event.sensor_type == SensorType.CAMERA:
                    # Compute Lane Keeping and Cruise Control
                    lane_keeping_correction = event.data_value * 0.1 # Placeholder logic
                    cruise_control_adjustment = event.data_value * 0.05 # Placeholder logic

                    self._log_feature_decision(timestamp, Feature.LANE_KEEPING, lane_keeping_correction)
                    self._log_command(timestamp, ActuatorID.STEERING_MOTOR, lane_keeping_correction)

                    self._log_feature_decision(timestamp, Feature.CRUISE_CONTROL, cruise_control_adjustment)
                    self._log_command(timestamp, ActuatorID.STEERING_MOTOR, cruise_control_adjustment) # Assuming steering motor also adjusts speed

            elif self._state == SystemState.DISENGAGED:
                # FR-02: data logged but no actuator commands or feature decisions
                pass # Already handled by emergency braking check

        # Handle driver events (FR-01, FR-03)
        elif isinstance(event, DriverEvent):
            if event.event_type == DriverEventType.ENGAGE:
                if self._state == SystemState.DISENGAGED:
                    self._log_state_change(timestamp, SystemState.ENGAGED, "Driver engaged system")
                    self._last_attentiveness_prompt_time = timestamp # Reset timer on engage
                
            elif event.event_type == DriverEventType.DISENGAGE:
                if self._state != SystemState.DISENGAGED:
                    self._log_state_change(timestamp, SystemState.DISENGAGED, "Driver disengaged system")

            elif event.event_type == DriverEventType.STEERING_FORCE:
                # This part specifically handles attentiveness response, override is already checked
                if self._state == SystemState.AWAITING_RESPONSE:
                    if event.value <= ATTENTIVENESS_VALID_RESPONSE_FORCE_N:
                        self._log_state_change(timestamp, SystemState.ENGAGED, "Attentiveness response received (force <= 3N)")
                        self._last_attentiveness_prompt_time = timestamp # Reset timer
                    elif event.value > ATTENTIVENESS_VALID_RESPONSE_FORCE_N and event.value <= DRIVER_OVERRIDE_FORCE_N:
                        # FR-03: 3N < force < 10N shall be ignored
                        print(f"[{timestamp:.2f}s] Attentiveness: Steering force {event.value}N ignored (3N < F <= 10N). Still awaiting response.")
                elif self._state == SystemState.ALARMING:
                    if event.value <= ATTENTIVENESS_VALID_RESPONSE_FORCE_N:
                        self._log_state_change(timestamp, SystemState.ENGAGED, "Alarm cleared by driver response (force <= 3N)")
                        self._last_attentiveness_prompt_time = timestamp # Reset timer

        # After processing event, check attentiveness again in case state changed
        self._handle_attentiveness_check(timestamp)

