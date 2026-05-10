"""Decision logic: the core state machine implementing the Copilot ADAS.

The behaviour mirrors the Alloy6 model in REQUIREMENTS.md section 2:
  - Events are processed in timestamp order.
  - Between consecutive events the simulation clock advances one tick at a time
    so that time-based internal transitions (attentiveness prompt → alarm) fire
    at the correct moment.
  - Sensor events (Lidar/Camera) drive emergency braking and lane/speed assist.
  - Driver events (ENGAGE/DISENGAGE/STEERING_FORCE) control engagement state.
"""
from __future__ import annotations

from typing import List, Union

from models import (
    ActuatorId, CommandEntry, Decision, DriverEvent, DriverEventType,
    Feature, FeatureDecisionEntry, SensorEvent, SensorType,
    State, StateLogEntry,
)

# ---------------------------------------------------------------------------
# Threshold constants (directly from the Alloy model)
# ---------------------------------------------------------------------------
LIDAR_DANGER: int = 5        # obstacle data_value below this triggers braking
OVERRIDE_FORCE: int = 10     # steering force above this immediately disengages
VALID_RESPONSE_FORCE: int = 3  # force at/below this is a valid attentiveness reply
PROMPT_INTERVAL: int = 120   # seconds of Engaged time before an attentiveness prompt
RESPONSE_WINDOW: int = 5     # seconds the driver has to respond before alarm fires


class CopilotStateMachine:
    """State machine for the Copilot ADAS as specified in the Alloy model."""

    def __init__(self) -> None:
        # Core simulation state (matches Alloy init predicate)
        self.current_state: State = State.DISENGAGED
        self.current_time: int = 0
        self.last_prompt: int = 0
        self.awaiting_since: int = 0

        # Output buffers written to CSV at the end
        self.state_log: List[StateLogEntry] = []
        self.commands_log: List[CommandEntry] = []
        self.feature_decisions: List[FeatureDecisionEntry] = []

    # ------------------------------------------------------------------
    # Low-level output helpers
    # ------------------------------------------------------------------

    def _log_state(self, t: int, prev: State, curr: State, trigger: str) -> None:
        self.state_log.append(StateLogEntry(t, prev, curr, trigger))

    def _emit_command(self, t: int, actuator: ActuatorId, values: str = "") -> None:
        self.commands_log.append(CommandEntry(t, actuator, values))

    def _emit_feature_decision(self, t: int, feature: Feature, decision: Decision) -> None:
        self.feature_decisions.append(FeatureDecisionEntry(t, feature, decision))

    # ------------------------------------------------------------------
    # Internal tick: time-based transitions (no event at this moment)
    # ------------------------------------------------------------------

    def _internal_tick(self, t: int) -> None:
        """Evaluate time-based transition rules for simulation tick t."""
        self.current_time = t

        if (self.current_state == State.ENGAGED
                and (t - self.last_prompt) >= PROMPT_INTERVAL):
            # Attentiveness prompt: Engaged long enough → AwaitingResponse
            prev = self.current_state
            self.current_state = State.AWAITING_RESPONSE
            self.awaiting_since = t
            self._log_state(t, prev, self.current_state, "attentiveness_prompt")
            self._emit_command(t, ActuatorId.STEERING_MOTOR, "PROMPT")

        elif (self.current_state == State.AWAITING_RESPONSE
              and (t - self.awaiting_since) >= RESPONSE_WINDOW):
            # Response timeout: driver did not react in time → Alarming
            prev = self.current_state
            self.current_state = State.ALARMING
            self._log_state(t, prev, self.current_state, "response_timeout")
            self._emit_command(t, ActuatorId.ALARM_ACTUATOR, "ALARM")

        elif self.current_state == State.ALARMING:
            # Alarm continues: emit one command per tick while alarming
            self._emit_command(t, ActuatorId.ALARM_ACTUATOR, "ALARM")
        # else: stutter — no state change, no output

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_engage(self, event: DriverEvent) -> None:
        """ENGAGE: Disengaged → Engaged (no-op if already engaged or alarming)."""
        if self.current_state == State.DISENGAGED:
            prev = self.current_state
            self.current_state = State.ENGAGED
            self.last_prompt = event.timestamp
            self._log_state(event.timestamp, prev, self.current_state, "ENGAGE")

    def _handle_disengage(self, event: DriverEvent) -> None:
        """DISENGAGE: any non-Disengaged state → Disengaged."""
        if self.current_state != State.DISENGAGED:
            prev = self.current_state
            self.current_state = State.DISENGAGED
            self._log_state(event.timestamp, prev, self.current_state, "DISENGAGE")

    def _handle_steering_force(self, event: DriverEvent) -> None:
        """STEERING_FORCE: effect depends on force magnitude and current state."""
        force = event.value if event.value is not None else 0.0

        if force > OVERRIDE_FORCE:
            # Hard override: any non-Disengaged state → Disengaged immediately
            if self.current_state != State.DISENGAGED:
                prev = self.current_state
                self.current_state = State.DISENGAGED
                self._log_state(event.timestamp, prev, self.current_state, "STEERING_FORCE")

        elif force <= VALID_RESPONSE_FORCE and self.current_state == State.AWAITING_RESPONSE:
            # Valid attentiveness response: AwaitingResponse → Engaged, reset timer
            prev = self.current_state
            self.current_state = State.ENGAGED
            self.last_prompt = event.timestamp
            self._log_state(event.timestamp, prev, self.current_state, "STEERING_FORCE")

        elif force <= VALID_RESPONSE_FORCE and self.current_state == State.ALARMING:
            # Alarm escape: Alarming → Engaged, reset timer
            prev = self.current_state
            self.current_state = State.ENGAGED
            self.last_prompt = event.timestamp
            self._log_state(event.timestamp, prev, self.current_state, "STEERING_FORCE")

        # Mid-range force while AwaitingResponse, or low force while Engaged/Disengaged: no-op

    def _handle_lidar(self, event: SensorEvent) -> None:
        """Lidar: data_value < LIDAR_DANGER triggers emergency braking (state-independent)."""
        if event.data_value < LIDAR_DANGER:
            self._emit_feature_decision(event.timestamp, Feature.EMERGENCY_BRAKING, Decision.BRAKE)
            self._emit_command(event.timestamp, ActuatorId.BRAKING_SYSTEM, "BRAKE")
        else:
            self._emit_feature_decision(event.timestamp, Feature.EMERGENCY_BRAKING, Decision.NO_BRAKE)

    def _handle_camera(self, event: SensorEvent) -> None:
        """Camera: lane keeping and cruise control, only when the system is Engaged."""
        if self.current_state == State.ENGAGED:
            self._emit_feature_decision(event.timestamp, Feature.LANE_KEEPING, Decision.ADJUST)
            self._emit_feature_decision(event.timestamp, Feature.CRUISE_CONTROL, Decision.ADJUST)
            self._emit_command(event.timestamp, ActuatorId.STEERING_MOTOR, "ADJUST")
            self._emit_command(event.timestamp, ActuatorId.SPEED_ACTUATOR, "ADJUST")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process_event(self, event: Union[SensorEvent, DriverEvent]) -> None:
        """Advance the clock to the event's timestamp and process the event.

        Internal ticks run for every integer second strictly between the last
        processed time and the event timestamp so that timer-based transitions
        fire at the correct moment before the event is handled.
        """
        # Run internal ticks for every tick before this event
        for t in range(self.current_time + 1, event.timestamp):
            self._internal_tick(t)

        self.current_time = event.timestamp

        if isinstance(event, DriverEvent):
            if event.event_type == DriverEventType.ENGAGE:
                self._handle_engage(event)
            elif event.event_type == DriverEventType.DISENGAGE:
                self._handle_disengage(event)
            elif event.event_type == DriverEventType.STEERING_FORCE:
                self._handle_steering_force(event)

        elif isinstance(event, SensorEvent):
            if event.sensor_type == SensorType.LIDAR:
                self._handle_lidar(event)
            elif event.sensor_type == SensorType.CAMERA:
                self._handle_camera(event)
