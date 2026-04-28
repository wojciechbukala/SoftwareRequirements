"""
Decision layer: the core state machine that implements Copilot's autonomous
driving logic as specified by the Alloy model.

Architecture
------------
The engine separates three concerns:
  * Perception  – handled by the caller (parser.py feeds typed events).
  * Decision    – this module; pure state-machine logic, no I/O.
  * Actuation   – the engine emits :class:`CommandEntry` records consumed
                  by the writer layer.

Timing model
------------
Event timestamps are used directly as the logical clock.  Between consecutive
events the engine runs internal "ticks" to detect time-based transitions:

  * Engaged for ≥ PROMPT_INTERVAL ticks  → AwaitingResponse + steering prompt.
  * AwaitingResponse for ≥ RESPONSE_WINDOW ticks → Alarming + alarm command.
  * Alarming → one AlarmActuator command per tick until a driver responds.
"""

from typing import List, Union

from .models import (
    Actuator,
    CommandEntry,
    Decision,
    DriverEvent,
    DriverEventType,
    Feature,
    FeatureDecisionEntry,
    SensorEvent,
    SensorType,
    State,
    StateLogEntry,
)

# ---------------------------------------------------------------------------
# Threshold constants (mirror the Alloy fun declarations)
# ---------------------------------------------------------------------------
LIDAR_DANGER: int = 5        # obstacle distance below which braking is triggered
OVERRIDE_FORCE: int = 10     # steering force that forces disengagement
VALID_RESPONSE_FORCE: int = 3  # max force accepted as a valid attentiveness response
PROMPT_INTERVAL: int = 120   # ticks between engagement and the next attentiveness check
RESPONSE_WINDOW: int = 5     # ticks the driver has to respond before alarming


class SimulationEngine:
    """
    Event-driven state machine for the Copilot ADAS system.

    Usage::

        engine = SimulationEngine()
        engine.run(sensor_events + driver_events)
        # inspect engine.state_log, engine.commands_log, engine.feature_decisions
    """

    def __init__(self) -> None:
        # Current autonomous state (mirrors Alloy's cs)
        self._state: State = State.DISENGAGED

        # Logical clock – the timestamp of the last processed step.
        # Starts at 0; advances with each event or internal transition.
        self._clock: int = 0

        # Clock value when the last attentiveness prompt was issued.
        # Initialised to 0 (same as Alloy's lastPrompt init).
        self._last_prompt: int = 0

        # Clock value when the system entered AwaitingResponse.
        self._awaiting_since: int = 0

        # Output buffers (read by the writer layer after run() completes)
        self.state_log: List[StateLogEntry] = []
        self.commands_log: List[CommandEntry] = []
        self.feature_decisions: List[FeatureDecisionEntry] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, events: List[Union[SensorEvent, DriverEvent]]) -> None:
        """
        Simulate the system over the provided event stream.

        Events are sorted internally by timestamp.  Unique timestamps are
        assumed (DA-04).  Internal time-based transitions are computed and
        emitted for every gap between consecutive events.
        """
        sorted_events = sorted(events, key=lambda e: e.timestamp)

        for event in sorted_events:
            # Process internal ticks in the open interval (clock, event.timestamp)
            self._advance_internal(event.timestamp - 1)
            # Dispatch the incoming event at its declared timestamp
            self._dispatch(event)

    # ------------------------------------------------------------------
    # Internal timing engine
    # ------------------------------------------------------------------

    def _advance_internal(self, end_time: int) -> None:
        """
        Execute internal (time-driven) transitions for every tick in
        [_clock + 1, end_time].

        The method jumps directly to the next interesting tick, so it runs
        in O(1) per transition for timed states and O(gap) only for ALARMING.
        """
        t = self._clock + 1
        while t <= end_time:
            if self._state == State.ENGAGED:
                prompt_at = self._last_prompt + PROMPT_INTERVAL
                if t >= prompt_at:
                    # Attentiveness prompt: Engaged → AwaitingResponse
                    self._emit_state(prompt_at, State.ENGAGED,
                                     State.AWAITING_RESPONSE, "ATTENTIVENESS_CHECK")
                    self._emit_command(prompt_at, Actuator.STEERING_MOTOR)
                    self._state = State.AWAITING_RESPONSE
                    self._awaiting_since = prompt_at
                    self._clock = prompt_at
                    t = prompt_at + 1
                elif prompt_at <= end_time:
                    # Jump directly to the tick where the prompt will fire
                    t = prompt_at
                else:
                    # Prompt fires after end_time; nothing to do in this gap
                    break

            elif self._state == State.AWAITING_RESPONSE:
                timeout_at = self._awaiting_since + RESPONSE_WINDOW
                if t >= timeout_at:
                    # Response timeout: AwaitingResponse → Alarming
                    self._emit_state(timeout_at, State.AWAITING_RESPONSE,
                                     State.ALARMING, "RESPONSE_TIMEOUT")
                    self._emit_command(timeout_at, Actuator.ALARM_ACTUATOR)
                    self._state = State.ALARMING
                    self._clock = timeout_at
                    t = timeout_at + 1
                elif timeout_at <= end_time:
                    # Jump directly to the tick where the timeout fires
                    t = timeout_at
                else:
                    # Timeout fires after end_time; nothing to do in this gap
                    break

            elif self._state == State.ALARMING:
                # One alarm command per tick while the alarm is active
                self._emit_command(t, Actuator.ALARM_ACTUATOR)
                self._clock = t
                t += 1

            else:
                # DISENGAGED: no internal transitions possible
                break

    # ------------------------------------------------------------------
    # Event dispatcher
    # ------------------------------------------------------------------

    def _dispatch(self, event: Union[SensorEvent, DriverEvent]) -> None:
        """Route an event to the appropriate handler."""
        self._clock = event.timestamp

        if isinstance(event, SensorEvent):
            if event.sensor_type == SensorType.LIDAR:
                self._handle_lidar(event)
            else:
                self._handle_camera(event)
        elif isinstance(event, DriverEvent):
            if event.event_type == DriverEventType.ENGAGE:
                self._handle_engage(event)
            elif event.event_type == DriverEventType.DISENGAGE:
                self._handle_disengage(event)
            elif event.event_type == DriverEventType.STEERING_FORCE:
                self._handle_steering_force(event)

    # ------------------------------------------------------------------
    # Driver event handlers
    # ------------------------------------------------------------------

    def _handle_engage(self, event: DriverEvent) -> None:
        """
        ENGAGE: Disengaged → Engaged.

        No-op if the system is already engaged or in any other active state.
        """
        if self._state == State.DISENGAGED:
            self._emit_state(event.timestamp, State.DISENGAGED, State.ENGAGED, "ENGAGE")
            self._state = State.ENGAGED
            self._last_prompt = event.timestamp

    def _handle_disengage(self, event: DriverEvent) -> None:
        """
        DISENGAGE: any active state → Disengaged.

        No-op if already Disengaged.
        """
        if self._state != State.DISENGAGED:
            self._emit_state(event.timestamp, self._state, State.DISENGAGED, "DISENGAGE")
            self._state = State.DISENGAGED

    def _handle_steering_force(self, event: DriverEvent) -> None:
        """
        STEERING_FORCE: evaluated in priority order (mirrors Alloy's
        mutually-exclusive implication chain).

        1. force > OVERRIDE_FORCE          → hard override, Disengaged.
        2. force ≤ VALID_RESPONSE_FORCE
           while AwaitingResponse          → valid response, Engaged.
        3. force ≤ VALID_RESPONSE_FORCE
           while Alarming                  → alarm escape, Engaged.
        4. VALID_RESPONSE_FORCE < force
           ≤ OVERRIDE_FORCE while
           AwaitingResponse               → mid-range ignored, no-op.
        5. all other combinations          → no-op.
        """
        force: float = event.value if event.value is not None else 0.0

        if force > OVERRIDE_FORCE:
            # Hard override: disengage regardless of current state
            if self._state != State.DISENGAGED:
                self._emit_state(event.timestamp, self._state,
                                 State.DISENGAGED, "STEERING_FORCE")
                self._state = State.DISENGAGED

        elif force <= VALID_RESPONSE_FORCE and self._state == State.AWAITING_RESPONSE:
            # Driver confirmed attentiveness
            self._emit_state(event.timestamp, State.AWAITING_RESPONSE,
                             State.ENGAGED, "STEERING_FORCE")
            self._state = State.ENGAGED
            self._last_prompt = event.timestamp

        elif force <= VALID_RESPONSE_FORCE and self._state == State.ALARMING:
            # Driver acknowledged the alarm
            self._emit_state(event.timestamp, State.ALARMING,
                             State.ENGAGED, "STEERING_FORCE")
            self._state = State.ENGAGED
            self._last_prompt = event.timestamp

        # Mid-range force while AwaitingResponse → intentional no-op (Alloy FR spec)
        # All other cases → no-op

    # ------------------------------------------------------------------
    # Sensor event handlers (perception → decision → actuation)
    # ------------------------------------------------------------------

    def _handle_lidar(self, event: SensorEvent) -> None:
        """
        Lidar reading: emergency-braking decision.

        Active in *all* states – safety-critical and state-independent.
        data_value < LIDAR_DANGER → BRAKE; otherwise → NO_BRAKE.
        """
        if event.data_value < LIDAR_DANGER:
            self._emit_decision(event.timestamp, Feature.EMERGENCY_BRAKING, Decision.BRAKE)
            self._emit_command(event.timestamp, Actuator.BRAKING_SYSTEM)
        else:
            self._emit_decision(event.timestamp, Feature.EMERGENCY_BRAKING, Decision.NO_BRAKE)

    def _handle_camera(self, event: SensorEvent) -> None:
        """
        Camera reading: lane-keeping and cruise-control adjustments.

        Only active while Engaged; suppressed in all other states.
        """
        if self._state == State.ENGAGED:
            self._emit_decision(event.timestamp, Feature.LANE_KEEPING, Decision.ADJUST)
            self._emit_decision(event.timestamp, Feature.CRUISE_CONTROL, Decision.ADJUST)
            self._emit_command(event.timestamp, Actuator.STEERING_MOTOR)
            self._emit_command(event.timestamp, Actuator.SPEED_ACTUATOR)

    # ------------------------------------------------------------------
    # Output emitters (actuator control layer interface)
    # ------------------------------------------------------------------

    def _emit_state(self, timestamp: int, prev: State, curr: State,
                    trigger: str) -> None:
        self.state_log.append(StateLogEntry(timestamp, prev, curr, trigger))

    def _emit_command(self, timestamp: int, actuator: Actuator) -> None:
        self.commands_log.append(CommandEntry(timestamp, actuator))

    def _emit_decision(self, timestamp: int, feature: Feature,
                       decision: Decision) -> None:
        self.feature_decisions.append(FeatureDecisionEntry(timestamp, feature, decision))
