"""
Decision layer: autonomous state machine implementing the Copilot logic.

The machine directly mirrors the Alloy model's state space and transition
predicates.  States, thresholds, and event-handler semantics are taken
verbatim from the formal specification.

State diagram
─────────────
  Disengaged ──[ENGAGE]──► Engaged
  Engaged ──[DISENGAGE / STEERING_FORCE > 10 N]──► Disengaged
  Engaged ──[PROMPT_TIMEOUT (120 s)]──► AwaitingResponse
  AwaitingResponse ──[RESPONSE_TIMEOUT (5 s)]──► Alarming
  AwaitingResponse ──[force ≤ 3 N]──► Engaged
  AwaitingResponse ──[STEERING_FORCE > 10 N]──► Disengaged
  Alarming ──[force ≤ 3 N]──► Engaged
  Alarming ──[STEERING_FORCE > 10 N]──► Disengaged
  Any active ──[DISENGAGE]──► Disengaged
"""

from enum import Enum
from typing import List, Union

from .actuator import CommandEntry, FeatureDecisionEntry, StateLogEntry
from .perception import AnyEvent, DriverEvent, DriverEventType, SensorEvent, SensorType

# ── Threshold constants (matching Alloy model) ────────────────────────────────

LIDAR_DANGER = 5.0
"""Obstacle distance (m) below which emergency braking is triggered."""

OVERRIDE_FORCE = 10.0
"""Steering force (N) above which the driver manually overrides autopilot."""

VALID_RESPONSE_FORCE = 3.0
"""Maximum steering force (N) that counts as a valid attentiveness response."""

PROMPT_INTERVAL = 120.0
"""Seconds of continuous Engaged operation before issuing an attentiveness prompt."""

RESPONSE_WINDOW = 5.0
"""Seconds the driver has to respond to an attentiveness prompt before alarming."""


# ── State enumeration ─────────────────────────────────────────────────────────

class State(Enum):
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"


# ── Core state machine ────────────────────────────────────────────────────────

class CopilotStateMachine:
    """
    Implements the Copilot autonomous driving state machine.

    Call :meth:`process_event` for each event in timestamp order.
    After the run, read :attr:`state_log`, :attr:`commands_log`, and
    :attr:`feature_decisions` for the output records.
    """

    def __init__(self) -> None:
        self.state: State = State.DISENGAGED
        self.current_time: float = 0.0
        # Timestamp of the last engage / prompt reset (used for PROMPT_INTERVAL check)
        self.last_prompt: float = 0.0
        # Timestamp when AwaitingResponse was entered (used for RESPONSE_WINDOW check)
        self.awaiting_since: float = 0.0

        self.state_log: List[StateLogEntry] = []
        self.commands_log: List[CommandEntry] = []
        self.feature_decisions: List[FeatureDecisionEntry] = []

    # ── Private helpers ───────────────────────────────────────────────────────

    def _transition(self, timestamp: float, new_state: State, trigger: str) -> None:
        """Record a state transition and update the current state."""
        self.state_log.append(
            StateLogEntry(
                timestamp=timestamp,
                previous_state=self.state.value,
                current_state=new_state.value,
                trigger_event=trigger,
            )
        )
        self.state = new_state

    def _emit_command(self, timestamp: float, actuator_id: str, values: str) -> None:
        self.commands_log.append(
            CommandEntry(timestamp=timestamp, actuator_id=actuator_id, values=values)
        )

    def _emit_feature_decision(self, timestamp: float, feature: str, decision: str) -> None:
        self.feature_decisions.append(
            FeatureDecisionEntry(timestamp=timestamp, feature=feature, decision=decision)
        )

    # ── Internal step (time-based transitions) ────────────────────────────────

    def _run_internal_checks(self, timestamp: float) -> None:
        """
        Apply time-driven internal transitions before processing an event at
        *timestamp*.  Mirrors the Alloy ``internalStep`` predicate.

        Checks are evaluated in priority order; a cascade (Engaged →
        AwaitingResponse → Alarming) is handled in a single call when both
        thresholds are exceeded by the same event timestamp.
        """
        # Track whether we were already in Alarming before this call so we can
        # distinguish "alarm tick" from "transition into Alarming".
        already_alarming = self.state is State.ALARMING

        # 1. Prompt timeout: Engaged too long without attentiveness confirmation.
        if (
            self.state is State.ENGAGED
            and timestamp >= self.last_prompt + PROMPT_INTERVAL
        ):
            trigger_time = self.last_prompt + PROMPT_INTERVAL
            self._transition(trigger_time, State.AWAITING_RESPONSE, "PROMPT_TIMEOUT")
            self.awaiting_since = trigger_time
            # Haptic/vibration cue via SteeringMotor
            self._emit_command(trigger_time, "SteeringMotor", "PROMPT")

        # 2. Response timeout: driver did not react within RESPONSE_WINDOW.
        #    Re-check state here because step 1 may have just changed it.
        if (
            self.state is State.AWAITING_RESPONSE
            and timestamp >= self.awaiting_since + RESPONSE_WINDOW
        ):
            trigger_time = self.awaiting_since + RESPONSE_WINDOW
            self._transition(trigger_time, State.ALARMING, "RESPONSE_TIMEOUT")
            self._emit_command(trigger_time, "AlarmActuator", "ALARM")
            # We just entered Alarming — the alarm tick below must not double-emit.
            already_alarming = False

        # 3. Alarm tick: continuously signal alarm while in Alarming state.
        #    Only fires if we were already Alarming before this check (not on
        #    the step that first entered Alarming, where the command above is
        #    already emitted).
        if already_alarming:
            self._emit_command(timestamp, "AlarmActuator", "ALARM")

    # ── Sensor event handlers ─────────────────────────────────────────────────

    def _handle_lidar(self, event: SensorEvent) -> None:
        """
        Emergency braking decision.

        A Lidar obstacle distance below LIDAR_DANGER triggers an emergency
        brake command regardless of the current operational state.
        """
        if event.data_value < LIDAR_DANGER:
            self._emit_feature_decision(event.timestamp, "EmergencyBraking", "BRAKE")
            self._emit_command(event.timestamp, "BrakingSystem", "BRAKE")
        else:
            self._emit_feature_decision(event.timestamp, "EmergencyBraking", "NO_BRAKE")

    def _handle_camera(self, event: SensorEvent) -> None:
        """
        Lane keeping and cruise control adjustments.

        Camera data is acted on only while the system is Engaged; in any
        other state the frame is silently discarded (no-op).
        """
        if self.state is State.ENGAGED:
            self._emit_feature_decision(event.timestamp, "LaneKeeping", "ADJUST")
            self._emit_feature_decision(event.timestamp, "CruiseControl", "ADJUST")
            self._emit_command(event.timestamp, "SteeringMotor", "ADJUST")
            self._emit_command(event.timestamp, "SpeedActuator", "ADJUST")

    # ── Driver event handlers ─────────────────────────────────────────────────

    def _handle_engage(self, event: DriverEvent) -> None:
        """ENGAGE: activate autopilot from Disengaged. No-op if already active."""
        if self.state is State.DISENGAGED:
            self._transition(event.timestamp, State.ENGAGED, "ENGAGE")
            self.last_prompt = event.timestamp

    def _handle_disengage(self, event: DriverEvent) -> None:
        """DISENGAGE: deactivate autopilot from any active state."""
        if self.state is not State.DISENGAGED:
            self._transition(event.timestamp, State.DISENGAGED, "DISENGAGE")

    def _handle_steering_force(self, event: DriverEvent) -> None:
        """
        STEERING_FORCE: interpret the applied force magnitude.

        force > OVERRIDE_FORCE          → manual override, disengage (FR-04)
        force ≤ VALID_RESPONSE_FORCE
          + AwaitingResponse            → valid attentiveness response → Engaged
          + Alarming                    → alarm escape → Engaged
        3 < force ≤ 10 + AwaitingResponse → ignored, keep waiting
        all other cases                 → no-op
        """
        force = event.value if event.value is not None else 0.0

        if force > OVERRIDE_FORCE:
            # Hard override: disengage immediately
            if self.state is not State.DISENGAGED:
                self._transition(event.timestamp, State.DISENGAGED, "STEERING_FORCE")

        elif force <= VALID_RESPONSE_FORCE and self.state is State.AWAITING_RESPONSE:
            # Driver confirmed attentiveness
            self._transition(event.timestamp, State.ENGAGED, "STEERING_FORCE")
            self.last_prompt = event.timestamp

        elif force <= VALID_RESPONSE_FORCE and self.state is State.ALARMING:
            # Driver reasserted control during alarm
            self._transition(event.timestamp, State.ENGAGED, "STEERING_FORCE")
            self.last_prompt = event.timestamp

        # Mid-range force (VALID_RESPONSE_FORCE < force ≤ OVERRIDE_FORCE) while
        # AwaitingResponse is deliberately ignored (keep waiting).
        # Low force in Disengaged or Engaged is also a no-op.

    # ── Public interface ──────────────────────────────────────────────────────

    def process_event(self, event: AnyEvent) -> None:
        """
        Process one event: run internal time-based checks then dispatch to the
        appropriate handler.

        Events must be delivered in non-decreasing timestamp order (guaranteed
        by :func:`~copilot.perception.merge_and_sort_events`).
        """
        self.current_time = event.timestamp
        self._run_internal_checks(event.timestamp)

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
