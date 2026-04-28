"""
Decision engine – the core state machine that processes events and produces
actuator commands and feature decisions.

This module is the direct translation of the Alloy model predicates into
executable Python.  It keeps the logic intentionally pure: it does not
perform any I/O and operates only on the :class:`SystemState` data structure.
"""

from typing import List, Union

from .models import (
    LIDAR_DANGER,
    OVERRIDE_FORCE,
    PROMPT_INTERVAL,
    RESPONSE_WINDOW,
    VALID_RESPONSE_FORCE,
    Actuator,
    CommandEntry,
    DecisionValue,
    DriverEvent,
    DriverEventType,
    Feature,
    FeatureDecisionEntry,
    SensorEvent,
    SensorType,
    State,
    StateLogEntry,
    SystemState,
)


class CopilotEngine:
    """
    Event-driven finite state machine for the Copilot ADAS system.

    Usage::

        engine = CopilotEngine()
        engine.process_events(events)
        state = engine.state  # inspect logs after processing
    """

    def __init__(self) -> None:
        self.state = SystemState()
        # Tracks the last processed timestamp so internal steps know the window.
        self._current_time: int = 0

    # ------------------------------------------------------------------
    # Private helpers – log / command emission
    # ------------------------------------------------------------------

    def _add_state_log(
        self,
        timestamp: int,
        previous: State,
        current: State,
        trigger: str,
    ) -> None:
        self.state.state_log.append(
            StateLogEntry(timestamp, previous, current, trigger)
        )

    def _emit_command(
        self, timestamp: int, actuator: Actuator, values: str = "ACTIVATE"
    ) -> None:
        self.state.commands_log.append(CommandEntry(timestamp, actuator, values))

    def _emit_feature_decision(
        self,
        timestamp: int,
        feature: Feature,
        decision: DecisionValue,
    ) -> None:
        self.state.feature_decision_log.append(
            FeatureDecisionEntry(timestamp, feature, decision)
        )

    # ------------------------------------------------------------------
    # Internal-step handler (time-based transitions between events)
    # ------------------------------------------------------------------

    def _process_internal_steps(self, up_to_time: int) -> None:
        """
        Advance internal-step logic for all timestamps in
        (self._current_time, up_to_time).

        Implements the ``internalStep`` predicate from the Alloy model:
        - Engaged for PROMPT_INTERVAL → AwaitingResponse
        - AwaitingResponse for RESPONSE_WINDOW → Alarming
        - Alarming → emit one AlarmActuator command per time unit
        """
        while True:
            cs = self.state.current_state

            if cs == State.ENGAGED:
                prompt_time = self.state.last_prompt + PROMPT_INTERVAL
                if prompt_time < up_to_time:
                    # Haptic cue to the driver (SteeringMotor vibration prompt)
                    self._emit_command(prompt_time, Actuator.STEERING_MOTOR, "HAPTIC_PROMPT")
                    self._add_state_log(
                        prompt_time, State.ENGAGED, State.AWAITING_RESPONSE, "PROMPT_TIMEOUT"
                    )
                    self.state.current_state = State.AWAITING_RESPONSE
                    self.state.awaiting_since = prompt_time
                    self._current_time = prompt_time
                    continue  # May immediately escalate to Alarming if window already passed
                else:
                    break  # Prompt not yet due; nothing more to do

            elif cs == State.AWAITING_RESPONSE:
                alarm_time = self.state.awaiting_since + RESPONSE_WINDOW
                if alarm_time < up_to_time:
                    self._emit_command(alarm_time, Actuator.ALARM_ACTUATOR, "ALARM")
                    self._add_state_log(
                        alarm_time,
                        State.AWAITING_RESPONSE,
                        State.ALARMING,
                        "RESPONSE_TIMEOUT",
                    )
                    self.state.current_state = State.ALARMING
                    self._current_time = alarm_time
                    continue  # Fall through to emit per-tick alarm commands
                else:
                    break  # Response window not yet expired; nothing more to do

            elif cs == State.ALARMING:
                # Emit one alarm command per time unit while the system remains in Alarming
                for t in range(self._current_time + 1, up_to_time):
                    self._emit_command(t, Actuator.ALARM_ACTUATOR, "ALARM")
                if up_to_time > self._current_time:
                    self._current_time = up_to_time - 1
                break

            else:
                # Disengaged or any other state: no internal transitions
                break

    # ------------------------------------------------------------------
    # External event handlers
    # ------------------------------------------------------------------

    def _handle_engage(self, event: DriverEvent) -> None:
        """Disengaged → Engaged; no-op in any other state."""
        if self.state.current_state == State.DISENGAGED:
            self._add_state_log(
                event.timestamp, State.DISENGAGED, State.ENGAGED, "ENGAGE"
            )
            self.state.current_state = State.ENGAGED
            self.state.last_prompt = event.timestamp

    def _handle_disengage(self, event: DriverEvent) -> None:
        """Any non-Disengaged state → Disengaged."""
        if self.state.current_state != State.DISENGAGED:
            prev = self.state.current_state
            self._add_state_log(
                event.timestamp, prev, State.DISENGAGED, "DISENGAGE"
            )
            self.state.current_state = State.DISENGAGED

    def _handle_steering_force(self, event: DriverEvent) -> None:
        """
        Process a STEERING_FORCE event (FR-04 override + attentiveness responses).

        - force > OVERRIDE_FORCE : manual override → Disengaged from any state
        - force ≤ VALID_RESPONSE_FORCE while AwaitingResponse : valid response → Engaged
        - force ≤ VALID_RESPONSE_FORCE while Alarming : alarm escape → Engaged
        - any other combination : no-op
        """
        force: float = event.value if event.value is not None else 0.0
        cs = self.state.current_state

        if force > OVERRIDE_FORCE:
            if cs != State.DISENGAGED:
                self._add_state_log(
                    event.timestamp, cs, State.DISENGAGED, "STEERING_FORCE_OVERRIDE"
                )
                self.state.current_state = State.DISENGAGED

        elif force <= VALID_RESPONSE_FORCE and cs == State.AWAITING_RESPONSE:
            self._add_state_log(
                event.timestamp,
                State.AWAITING_RESPONSE,
                State.ENGAGED,
                "STEERING_FORCE_RESPONSE",
            )
            self.state.current_state = State.ENGAGED
            self.state.last_prompt = event.timestamp

        elif force <= VALID_RESPONSE_FORCE and cs == State.ALARMING:
            self._add_state_log(
                event.timestamp,
                State.ALARMING,
                State.ENGAGED,
                "STEERING_FORCE_RESPONSE",
            )
            self.state.current_state = State.ENGAGED
            self.state.last_prompt = event.timestamp
        # All other combinations (mid-range force in AwaitingResponse, etc.) → no-op

    def _handle_lidar(self, event: SensorEvent) -> None:
        """
        Emergency braking decision based on Lidar obstacle distance.

        data_value < LIDAR_DANGER → BRAKE + BrakingSystem command
        data_value ≥ LIDAR_DANGER → NO_BRAKE (no actuator command)
        """
        if event.data_value < LIDAR_DANGER:
            self._emit_feature_decision(
                event.timestamp, Feature.EMERGENCY_BRAKING, DecisionValue.BRAKE
            )
            self._emit_command(event.timestamp, Actuator.BRAKING_SYSTEM, "BRAKE")
        else:
            self._emit_feature_decision(
                event.timestamp, Feature.EMERGENCY_BRAKING, DecisionValue.NO_BRAKE
            )

    def _handle_camera(self, event: SensorEvent) -> None:
        """
        Lane-keeping and cruise-control decisions from camera data.

        Only active while the system is in the Engaged state.
        Produces LaneKeeping=ADJUST and CruiseControl=ADJUST decisions plus
        SteeringMotor and SpeedActuator commands.
        """
        if self.state.current_state == State.ENGAGED:
            self._emit_feature_decision(
                event.timestamp, Feature.LANE_KEEPING, DecisionValue.ADJUST
            )
            self._emit_feature_decision(
                event.timestamp, Feature.CRUISE_CONTROL, DecisionValue.ADJUST
            )
            self._emit_command(event.timestamp, Actuator.STEERING_MOTOR, "ADJUST")
            self._emit_command(event.timestamp, Actuator.SPEED_ACTUATOR, "ADJUST")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process_events(
        self, events: List[Union[SensorEvent, DriverEvent]]
    ) -> SystemState:
        """
        Drive the simulation by processing every event in chronological order.

        Between consecutive events the engine runs internal-step logic to handle
        time-based state transitions (attentiveness prompts, response timeouts,
        ongoing alarm emission).

        Returns the :class:`SystemState` containing all populated output logs.
        """
        for event in events:
            # Run internal (time-based) transitions for the interval before this event
            self._process_internal_steps(event.timestamp)
            self._current_time = event.timestamp

            if isinstance(event, SensorEvent):
                if event.sensor_type == SensorType.LIDAR:
                    self._handle_lidar(event)
                elif event.sensor_type == SensorType.CAMERA:
                    self._handle_camera(event)

            elif isinstance(event, DriverEvent):
                if event.event_type == DriverEventType.ENGAGE:
                    self._handle_engage(event)
                elif event.event_type == DriverEventType.DISENGAGE:
                    self._handle_disengage(event)
                elif event.event_type == DriverEventType.STEERING_FORCE:
                    self._handle_steering_force(event)

        return self.state
