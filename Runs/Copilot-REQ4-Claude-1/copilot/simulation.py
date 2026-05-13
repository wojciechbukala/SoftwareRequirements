"""Simulation engine: state machine and event-processing loop.

The engine mirrors the Alloy6 model exactly:
  - States:   Disengaged / Engaged / AwaitingResponse / Alarming
  - Constants are taken directly from the Alloy fun declarations.
  - External events (sensor + driver) are processed in timestamp order.
  - Between consecutive external events the engine fires any time-based
    internal transitions (prompt, response timeout, alarm tick).
"""

from typing import List, Union

from . import actuator as act
from . import decision as dec
from .models import (
    CommandEntry,
    DriverEvent,
    DriverEventType,
    FeatureDecisionEntry,
    SensorEvent,
    SensorType,
    State,
    StateLogEntry,
)

# ── Threshold constants (match Alloy model) ──────────────────────────────────
LIDAR_DANGER_THRESHOLD: float = 5.0    # fun LIDAR_DANGER
OVERRIDE_FORCE: float = 10.0           # fun OVERRIDE_FORCE
VALID_RESPONSE_FORCE: float = 3.0      # fun VALID_RESPONSE_FORCE
PROMPT_INTERVAL: float = 120.0         # fun PROMPT_INTERVAL (seconds)
RESPONSE_WINDOW: float = 5.0           # fun RESPONSE_WINDOW (seconds)

AnyEvent = Union[SensorEvent, DriverEvent]


class Simulation:
    """Event-driven simulation of the Copilot on-board computer."""

    def __init__(self) -> None:
        # Initial state mirrors the Alloy init predicate
        self._state: State = State.DISENGAGED
        self._last_prompt: float = 0.0
        self._awaiting_since: float = 0.0

        # Output accumulators
        self.state_log: List[StateLogEntry] = []
        self.commands_log: List[CommandEntry] = []
        self.feature_decisions: List[FeatureDecisionEntry] = []

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _transition(self, timestamp: float, new_state: State, trigger: str) -> None:
        """Record a state transition and update the current state."""
        self.state_log.append(
            StateLogEntry(
                timestamp=timestamp,
                previous_state=self._state.value,
                current_state=new_state.value,
                trigger_event=trigger,
            )
        )
        self._state = new_state

    def _emit_command(self, entry: CommandEntry) -> None:
        self.commands_log.append(entry)

    def _emit_decision(self, entry: FeatureDecisionEntry) -> None:
        self.feature_decisions.append(entry)

    # ── Internal (time-based) transitions ────────────────────────────────────

    def _fire_internal_transitions(self, up_to_time: float) -> None:
        """Fire any time-based transitions whose computed time is < *up_to_time*.

        Two cascading checks are performed so that Engaged → AwaitingResponse →
        Alarming can collapse into a single inter-event gap if enough time passes.
        The alarm tick for the Alarming state is handled separately in *run()*.
        """
        # 1. Engaged → AwaitingResponse after PROMPT_INTERVAL
        if self._state is State.ENGAGED:
            prompt_time = self._last_prompt + PROMPT_INTERVAL
            if prompt_time < up_to_time:
                self._transition(prompt_time, State.AWAITING_RESPONSE, "PROMPT_TIMEOUT")
                self._emit_command(act.command_attentiveness_prompt(prompt_time))
                self._awaiting_since = prompt_time

        # 2. AwaitingResponse → Alarming after RESPONSE_WINDOW
        if self._state is State.AWAITING_RESPONSE:
            alarm_time = self._awaiting_since + RESPONSE_WINDOW
            if alarm_time < up_to_time:
                self._transition(alarm_time, State.ALARMING, "RESPONSE_TIMEOUT")
                self._emit_command(act.command_alarm(alarm_time))

    # ── Sensor event handlers (perception → decision → actuator) ─────────────

    def _handle_lidar(self, event: SensorEvent) -> None:
        """Process a Lidar reading unconditionally (emergency braking ignores state)."""
        fd = dec.evaluate_emergency_braking(event)
        self._emit_decision(fd)
        if fd.decision == "BRAKE":
            self._emit_command(act.command_brake(event.timestamp))

    def _handle_camera(self, event: SensorEvent) -> None:
        """Process a Camera reading; lane-keeping and cruise-control only when Engaged."""
        if self._state is not State.ENGAGED:
            return
        self._emit_decision(dec.evaluate_lane_keeping(event))
        self._emit_decision(dec.evaluate_cruise_control(event))
        self._emit_command(act.command_steering_adjust(event.timestamp))
        self._emit_command(act.command_speed_adjust(event.timestamp))

    # ── Driver event handlers ─────────────────────────────────────────────────

    def _handle_engage(self, event: DriverEvent) -> None:
        """ENGAGE: Disengaged → Engaged (no-op if already engaged)."""
        if self._state is State.DISENGAGED:
            self._transition(event.timestamp, State.ENGAGED, "ENGAGE")
            # Reset attentiveness prompt countdown from the moment of engagement
            self._last_prompt = event.timestamp

    def _handle_disengage(self, event: DriverEvent) -> None:
        """DISENGAGE: any non-Disengaged state → Disengaged."""
        if self._state is not State.DISENGAGED:
            self._transition(event.timestamp, State.DISENGAGED, "DISENGAGE")

    def _handle_steering_force(self, event: DriverEvent) -> None:
        """STEERING_FORCE: handle override, valid response, and alarm escape.

        FR-04 override  : force > OVERRIDE_FORCE  → Disengaged from any state.
        Valid response  : force ≤ VALID_RESPONSE_FORCE while AwaitingResponse → Engaged.
        Alarm escape    : force ≤ VALID_RESPONSE_FORCE while Alarming → Engaged.
        Mid-range force : no state change (driver not fully responding, not overriding).
        """
        force = event.value if event.value is not None else 0.0

        if force > OVERRIDE_FORCE:
            # Manual override — disengage immediately regardless of current state
            if self._state is not State.DISENGAGED:
                self._transition(event.timestamp, State.DISENGAGED, "STEERING_FORCE")

        elif force <= VALID_RESPONSE_FORCE and self._state is State.AWAITING_RESPONSE:
            # Driver confirmed attentiveness
            self._transition(event.timestamp, State.ENGAGED, "STEERING_FORCE")
            self._last_prompt = event.timestamp

        elif force <= VALID_RESPONSE_FORCE and self._state is State.ALARMING:
            # Driver intervenes to suppress alarm
            self._transition(event.timestamp, State.ENGAGED, "STEERING_FORCE")
            self._last_prompt = event.timestamp

        # Mid-range force while AwaitingResponse (or any other combination) → no-op

    # ── Main simulation loop ──────────────────────────────────────────────────

    def run(self, events: List[AnyEvent]) -> None:
        """Process all events, producing state_log, commands_log, and feature_decisions.

        Algorithm
        ---------
        1. Sort events by timestamp (unique per DA-04).
        2. Before each event, fire any overdue internal transitions.
        3. If currently Alarming, emit one alarm command at the event's timestamp
           (models the continuous alarm tick from the Alloy internalStep).
        4. Dispatch the event to the appropriate handler.
        """
        sorted_events = sorted(events, key=lambda e: e.timestamp)

        for event in sorted_events:
            # Step A: fire internal transitions that fell due before this event
            self._fire_internal_transitions(event.timestamp)

            # Step B: if alarming, emit a continuous alarm tick at this timestamp
            if self._state is State.ALARMING:
                self._emit_command(act.command_alarm(event.timestamp))

            # Step C: dispatch external event
            if isinstance(event, SensorEvent):
                if event.sensor_type is SensorType.LIDAR:
                    self._handle_lidar(event)
                elif event.sensor_type is SensorType.CAMERA:
                    self._handle_camera(event)

            elif isinstance(event, DriverEvent):
                if event.event_type is DriverEventType.ENGAGE:
                    self._handle_engage(event)
                elif event.event_type is DriverEventType.DISENGAGE:
                    self._handle_disengage(event)
                elif event.event_type is DriverEventType.STEERING_FORCE:
                    self._handle_steering_force(event)
