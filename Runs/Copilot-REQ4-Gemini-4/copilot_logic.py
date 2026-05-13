import math
from collections import namedtuple
from typing import List, Union

from copilot_constants import (
    State, SensorType, DriverEventType, FeatureDecisionKind, DecisionValue, Actuator,
    LIDAR_DANGER, OVERRIDE_FORCE, VALID_RESPONSE_FORCE, PROMPT_INTERVAL, RESPONSE_WINDOW
)
from copilot_csv_handler import SensorEventData, DriverEventData, StateLogEntry, CommandLogEntry, FeatureDecisionLogEntry


class CopilotSystem:
    """
    Simulates the Copilot system based on the provided Alloy model.
    Manages system state, processes events, and logs decisions and commands.
    """

    def __init__(self):
        """
        Initializes the system state as per the Alloy 'init' predicate.
        """
        self.current_state: State = State.DISENGAGED
        self.current_time: float = 0.0
        self.last_prompt: float = 0.0
        self.awaiting_since: float = 0.0

        self.state_log: List[StateLogEntry] = []
        self.commands_log: List[CommandLogEntry] = []
        self.feature_decision_log: List[FeatureDecisionLogEntry] = []
        self.processed_events: List[Union[SensorEventData, DriverEventData]] = []

    def _add_state_log(self, timestamp: float, previous_state: State, current_state: State, trigger_event: str):
        """Appends a state transition entry to the state log."""
        self.state_log.append(StateLogEntry(timestamp, previous_state, current_state, trigger_event))

    def _emit_command(self, timestamp: float, actuator_id: Actuator, values: Union[str, float] = ""):
        """Appends a command entry to the commands log."""
        self.commands_log.append(CommandLogEntry(timestamp, actuator_id, values))

    def _emit_feature_decision(self, timestamp: float, feature: FeatureDecisionKind, decision: DecisionValue):
        """Appends a feature decision entry to the feature decision log."""
        self.feature_decision_log.append(FeatureDecisionLogEntry(timestamp, feature, decision))

    def _tick_time(self, increment: float = 1.0):
        """Advances the discrete clock."""
        self.current_time += increment

    def _process_event(self, event: Union[SensorEventData, DriverEventData]):
        """Marks an event as processed."""
        self.processed_events.append(event)

    def _transition_state(self, new_state: State, timestamp: float, trigger_event: str):
        """Helper to transition state and log the change."""
        if self.current_state != new_state:
            self._add_state_log(timestamp, self.current_state, new_state, trigger_event)
            self.current_state = new_state

    # --- EVENT HANDLERS ---

    def _handle_engage_driver_event(self, event: DriverEventData):
        """Handles an ENGAGE driver event."""
        if self.current_state == State.DISENGAGED:
            self._transition_state(State.ENGAGED, event.timestamp, event.event_type.value)
            self.last_prompt = event.timestamp # Reset last prompt to current time
            # awaiting_since remains 0 (initial or reset)
        # else: no-op as per Alloy model if not Disengaged

    def _handle_disengage_driver_event(self, event: DriverEventData):
        """Handles a DISENGAGE driver event."""
        if self.current_state != State.DISENGAGED:
            self._transition_state(State.DISENGAGED, event.timestamp, event.event_type.value)
            # last_prompt and awaiting_since retain their values
        # else: no-op as per Alloy model if already Disengaged

    def _handle_steering_force_driver_event(self, event: DriverEventData):
        """Handles a STEERING_FORCE driver event."""
        force = event.value
        if force is None: # Should not happen if parsing is correct, but defensive.
            return

        # Override: force > OVERRIDE_FORCE, any state -> Disengaged (FR-04)
        if force > OVERRIDE_FORCE:
            if self.current_state != State.DISENGAGED:
                self._transition_state(State.DISENGAGED, event.timestamp, f"{event.event_type.value}:{force}")
            return # Override takes precedence

        # Valid response while AwaitingResponse -> Engaged, reset prompt timer
        if force <= VALID_RESPONSE_FORCE and self.current_state == State.AWAITING_RESPONSE:
            self._transition_state(State.ENGAGED, event.timestamp, f"{event.event_type.value}:{force}")
            self.last_prompt = event.timestamp
            self.awaiting_since = 0.0 # Reset
            return

        # Alarm escape: low force while Alarming -> Engaged, reset prompt timer
        if force <= VALID_RESPONSE_FORCE and self.current_state == State.ALARMING:
            self._transition_state(State.ENGAGED, event.timestamp, f"{event.event_type.value}:{force}")
            self.last_prompt = event.timestamp
            self.awaiting_since = 0.0 # Reset
            return

        # Ignored mid-range force while AwaitingResponse -> no-op, keep waiting
        # (force > VALID_RESPONSE_FORCE and force <= OVERRIDE_FORCE and self.current_state == State.AWAITING_RESPONSE)
        # This condition implicitly results in no-op if the above don't match, so no explicit action needed.

        # Other cases (e.g., low force in Disengaged/Engaged) -> no-op. Also implicit.

    def _handle_lidar_sensor_event(self, event: SensorEventData):
        """Handles a Lidar sensor event."""
        if event.data_value < LIDAR_DANGER:
            self._emit_feature_decision(event.timestamp, FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.BRAKE)
            self._emit_command(event.timestamp, Actuator.BRAKING_SYSTEM)
        else:
            self._emit_feature_decision(event.timestamp, FeatureDecisionKind.EMERGENCY_BRAKING, DecisionValue.NO_BRAKE)

    def _handle_camera_sensor_event(self, event: SensorEventData):
        """Handles a Camera sensor event."""
        if self.current_state == State.ENGAGED:
            # Emit two feature decisions (LaneKeeping + CruiseControl)
            self._emit_feature_decision(event.timestamp, FeatureDecisionKind.LANE_KEEPING, DecisionValue.ADJUST)
            self._emit_feature_decision(event.timestamp, FeatureDecisionKind.CRUISE_CONTROL, DecisionValue.ADJUST)
            # Emit two commands (SteeringMotor + SpeedActuator)
            self._emit_command(event.timestamp, Actuator.STEERING_MOTOR)
            self._emit_command(event.timestamp, Actuator.SPEED_ACTUATOR)
        # else: no-op (no decisions/commands emitted if not Engaged)

    # --- STEP PREDICATES ---

    def _step(self, event: Union[SensorEventData, DriverEventData]):
        """Dispatches event to the appropriate handler."""
        self._process_event(event) # Mark event as processed

        if isinstance(event, SensorEventData):
            if event.sensor_type == SensorType.LIDAR:
                self._handle_lidar_sensor_event(event)
            elif event.sensor_type == SensorType.CAMERA:
                self._handle_camera_sensor_event(event)
        elif isinstance(event, DriverEventData):
            if event.event_type == DriverEventType.ENGAGE:
                self._handle_engage_driver_event(event)
            elif event.event_type == DriverEventType.DISENGAGE:
                self._handle_disengage_driver_event(event)
            elif event.event_type == DriverEventType.STEERING_FORCE:
                self._handle_steering_force_driver_event(event)
        # Time will be advanced by the main loop to match event.timestamp

    def _internal_step(self, target_time: float):
        """
        Processes internal state transitions until current_time reaches target_time.
        This handles prompts, timeouts, and alarms.
        """
        while self.current_time < target_time:
            next_time = self.current_time + 1.0 # Assume discrete ticks for internal processing, 1 unit of time

            state_changed_internally = False
            trigger_event_str = ""

            # prompt: Engaged long enough since last prompt -> AwaitingResponse
            if (self.current_state == State.ENGAGED and
                    (self.current_time - self.last_prompt) >= PROMPT_INTERVAL):
                self._transition_state(State.AWAITING_RESPONSE, self.current_time, "PROMPT_TIMEOUT")
                self.awaiting_since = self.current_time
                self._emit_command(self.current_time, Actuator.STEERING_MOTOR, "PROMPT") # Alloy says SteeringMotor for prompt
                state_changed_internally = True

            # response timeout: AwaitingResponse longer than window -> Alarming
            elif (self.current_state == State.AWAITING_RESPONSE and
                  (self.current_time - self.awaiting_since) >= RESPONSE_WINDOW):
                self._transition_state(State.ALARMING, self.current_time, "RESPONSE_TIMEOUT")
                self._emit_command(self.current_time, Actuator.ALARM_ACTUATOR, "ALARM")
                state_changed_internally = True

            # alarm tick: keep Alarming, emit one alarm command per tick
            elif self.current_state == State.ALARMING:
                self._emit_command(self.current_time, Actuator.ALARM_ACTUATOR, "ALARM_TICK")
                state_changed_internally = True # Even if state doesn't change, command is emitted

            if state_changed_internally:
                # If an internal action happened at current_time, ensure next_time is at least current_time + 1
                # or just advance the clock by 1 after the internal step logic.
                # The Alloy model assumes `tickTime` after each internal step leading to new values,
                # but we are doing it in a `while` loop that increments `current_time` to reach `target_time`.
                # If internal actions change state at current_time, the current_time should immediately be available
                # for the next internal step. The `_tick_time` should happen at the end of the full internal step.
                pass # State change already logged with current_time

            self.current_time += 1.0 # Advance time by 1 unit for internal steps

            # If an internal state change occurred, we should re-evaluate for the *next* internal step
            # at the new current_time. If no internal change, then this loop will just tick time
            # until target_time.
            # This loop ensures that all internal transitions that *can* happen at or before target_time,
            # are evaluated and processed.

    def process_all_events(self, all_events: List[Union[SensorEventData, DriverEventData]]):
        """
        Main processing loop for all events.
        Events are sorted by timestamp. Internal steps are handled between external events.
        """
        # Sort events by timestamp
        sorted_events = sorted(all_events, key=lambda x: x.timestamp)

        for event in sorted_events:
            # Advance time and handle internal steps until the event's timestamp is reached
            if self.current_time < event.timestamp:
                self._internal_step(event.timestamp)
            
            # Ensure current_time does not exceed event.timestamp immediately after internal steps
            self.current_time = event.timestamp

            # Process the external event
            self._step(event)

            # After processing the event, check for immediate internal steps at the same timestamp
            # The Alloy model implies that internal actions can happen AT the current time.
            # However, prompt and timeout conditions are `currentTime >= plus[lastPrompt, PROMPT_INTERVAL]`
            # or `currentTime >= plus[awaitingSince, RESPONSE_WINDOW]`.
            # If current_time was advanced to event.timestamp, and this makes a condition true,
            # it should be handled.
            # To handle this, we effectively call _internal_step with a small increment beyond current_time,
            # allowing it to check conditions at event.timestamp + 1 (or the next available tick).
            # This is a subtle point about discrete time in Alloy vs. continuous time in Python.
            # For simplicity and to match the 'tickTime' and sequential nature,
            # I will ensure that after an event is processed, internal steps are checked
            # for the time *after* the event.
            self.current_time = event.timestamp # Ensure current_time aligns with the event after processing

        # After all external events are processed, continue with internal steps
        # indefinitely until no further state changes or commands are emitted.
        # Alloy's 'Termination' fact indicates stutter if no pending events and not Alarming.
        # We simulate this by checking for internal state changes.
        last_state = self.current_state
        last_log_count = len(self.state_log) + len(self.commands_log) + len(self.feature_decision_log)
        
        # To prevent infinite loop in case of continuous alarming, we might need a max_ticks limit
        max_post_processing_ticks = 1000 # Arbitrary limit
        tick_count = 0

        while tick_count < max_post_processing_ticks:
            prev_current_time = self.current_time
            prev_state = self.current_state
            
            # Check for prompt, timeout, or alarm conditions at the current time + 1
            # To match Alloy's "tickTime" leading to new state/commands,
            # we consider the *next* time point for these checks.
            # This ensures any actions that become due *at* the previous event's timestamp
            # or in the intervals between events are processed correctly.
            
            # We explicitly advance time by 1 unit for internal steps to allow conditions to be met
            # at PROMPT_INTERVAL/RESPONSE_WINDOW, mirroring the discrete nature.
            self.current_time += 1.0 
            
            state_changed_this_tick = False
            commands_emitted_this_tick = 0
            
            # Prompt check
            if (self.current_state == State.ENGAGED and
                    (self.current_time - self.last_prompt) >= PROMPT_INTERVAL):
                self._transition_state(State.AWAITING_RESPONSE, self.current_time, "PROMPT_TIMEOUT")
                self.awaiting_since = self.current_time
                self._emit_command(self.current_time, Actuator.STEERING_MOTOR, "PROMPT")
                state_changed_this_tick = True
                commands_emitted_this_tick += 1

            # Timeout check (only if not just transitioned to AWAITING_RESPONSE)
            if (self.current_state == State.AWAITING_RESPONSE and
                (self.current_time - self.awaiting_since) >= RESPONSE_WINDOW):
                self._transition_state(State.ALARMING, self.current_time, "RESPONSE_TIMEOUT")
                self._emit_command(self.current_time, Actuator.ALARM_ACTUATOR, "ALARM")
                state_changed_this_tick = True
                commands_emitted_this_tick += 1
            
            # Alarming tick (continuously emit alarm if state is Alarming)
            if self.current_state == State.ALARMING and not state_changed_this_tick:
                 # If previous conditions didn't change state, but it was already Alarming
                self._emit_command(self.current_time, Actuator.ALARM_ACTUATOR, "ALARM_TICK")
                commands_emitted_this_tick += 1


            # If no internal actions (state change or command emission) occurred in this tick,
            # and there are no pending external events, the system stutters.
            if not state_changed_this_tick and commands_emitted_this_tick == 0:
                # No further internal actions possible, stop post-processing
                self.current_time = prev_current_time # Revert time to before this non-action tick
                break

            tick_count += 1
        
        if tick_count >= max_post_processing_ticks:
            print(f"Warning: Reached maximum post-processing ticks ({max_post_processing_ticks}). System might be in a continuous alarming state.")
