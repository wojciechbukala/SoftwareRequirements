"""Decision logic: system state machine and event dispatcher (FR-01 through FR-04)."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from copilot import actuators, features
from copilot.output import OutputWriter


# ---------------------------------------------------------------------------
# State enumeration
# ---------------------------------------------------------------------------

class State(Enum):
    """All operating modes that Copilot can occupy (FR-01)."""
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"


# ---------------------------------------------------------------------------
# Trigger labels written to state_log.csv
# ---------------------------------------------------------------------------

TRIGGER_ENGAGE = "ENGAGE"
TRIGGER_DISENGAGE = "DISENGAGE"
TRIGGER_DRIVER_OVERRIDE = "DRIVER_OVERRIDE"
TRIGGER_ATTENTIVENESS_PROMPT = "ATTENTIVENESS_PROMPT"
TRIGGER_VALID_RESPONSE = "VALID_RESPONSE"
TRIGGER_RESPONSE_TIMEOUT = "RESPONSE_TIMEOUT"

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# Seconds between consecutive attentiveness prompts (FR-03).
ATTENTIVENESS_INTERVAL_S = 120.0

# Seconds the driver has to respond after a prompt (FR-03).
RESPONSE_WINDOW_S = 5.0

# Wheel force (N) at or below which a driver response is considered valid (FR-03).
VALID_RESPONSE_MAX_FORCE_N = 3.0

# Wheel force (N) strictly above which a driver override is triggered (FR-04).
OVERRIDE_MIN_FORCE_N = 10.0


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class CopilotStateMachine:
    """Maintains operating mode and dispatches events to the appropriate handlers.

    The machine relies on an OutputWriter for all I/O side-effects so that the
    decision logic remains independent of file handling.
    """

    def __init__(self, writer: OutputWriter) -> None:
        self._state: State = State.DISENGAGED
        self._writer = writer

        # Timestamp of the last attentiveness prompt (or engagement); used to
        # schedule the next prompt when in ENGAGED state.
        self._last_prompt_ts: Optional[float] = None

        # Timestamp at which the system entered AWAITING_RESPONSE; used to
        # detect response-window expiry.
        self._awaiting_start_ts: Optional[float] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def state(self) -> State:
        return self._state

    def process_event(self, kind: str, event) -> None:
        """Dispatch one event from the merged stream (PF-02).

        Args:
            kind:  "sensor" or "driver"
            event: SensorEvent or DriverEvent instance
        """
        ts: float = event.timestamp

        # Timer-based transitions must be evaluated before the event itself so
        # that expired windows are closed before a new stimulus is processed.
        self._check_timers(ts)

        if kind == "sensor":
            self._handle_sensor(ts, event)
        else:
            self._handle_driver(ts, event)

    # ------------------------------------------------------------------
    # Timer checks
    # ------------------------------------------------------------------

    def _check_timers(self, ts: float) -> None:
        """Evaluate time-based state transitions that may be due at timestamp ts."""

        # AwaitingResponse timeout → Alarming (FR-03)
        if (
            self._state is State.AWAITING_RESPONSE
            and self._awaiting_start_ts is not None
            and ts > self._awaiting_start_ts + RESPONSE_WINDOW_S
        ):
            self._transition(State.ALARMING, ts, TRIGGER_RESPONSE_TIMEOUT)
            self._writer.record_command(ts, actuators.ALARM_ACTUATOR, actuators.continuous_alarm_command())

        # Engaged attentiveness prompt due (FR-03)
        if (
            self._state is State.ENGAGED
            and self._last_prompt_ts is not None
            and ts >= self._last_prompt_ts + ATTENTIVENESS_INTERVAL_S
        ):
            self._writer.record_command(ts, actuators.STEERING_MOTOR, actuators.attentiveness_prompt_command())
            self._transition(State.AWAITING_RESPONSE, ts, TRIGGER_ATTENTIVENESS_PROMPT)
            self._awaiting_start_ts = ts
            # Reset anchor so the next 120 s window starts from the prompt time.
            self._last_prompt_ts = ts

    # ------------------------------------------------------------------
    # Sensor event handler (PF-01)
    # ------------------------------------------------------------------

    def _handle_sensor(self, ts: float, event) -> None:
        sensor_type = event.sensor_type.lower()

        if sensor_type == "lidar":
            self._evaluate_emergency_braking(ts, event.data_value)

        elif sensor_type == "camera":
            # Camera features are only active in Engaged mode (PF-01, FR-02).
            if self._state is State.ENGAGED:
                self._evaluate_camera_features(ts, event.data_value)

    def _evaluate_emergency_braking(self, ts: float, distance_m: float) -> None:
        """Evaluate Lidar-based emergency braking regardless of operating mode (FR-02)."""
        should_brake, label = features.evaluate_emergency_braking(distance_m)
        self._writer.record_feature_decision(ts, "EmergencyBraking", label)

        if should_brake:
            self._writer.record_command(ts, actuators.BRAKING_SYSTEM, actuators.brake_command())
            # Skip remaining features for this cycle when braking (FR-02).

    def _evaluate_camera_features(self, ts: float, camera_value: float) -> None:
        """Compute lane keeping and cruise control for a camera reading (FR-02)."""
        correction = features.compute_lane_keeping_correction(camera_value)
        adjustment = features.compute_cruise_control_adjustment(camera_value)

        # Feature decisions (FR-02)
        self._writer.record_feature_decision(ts, "LaneKeeping", f"correction={correction}")
        self._writer.record_feature_decision(ts, "CruiseControl", f"adjustment={adjustment}")

        # Actuator commands (FR-02)
        self._writer.record_command(ts, actuators.STEERING_MOTOR, actuators.lane_correction_command(correction))
        self._writer.record_command(ts, actuators.SPEED_ACTUATOR, actuators.speed_adjustment_command(adjustment))

    # ------------------------------------------------------------------
    # Driver event handler (FR-01, FR-03, FR-04)
    # ------------------------------------------------------------------

    def _handle_driver(self, ts: float, event) -> None:
        etype = event.event_type

        if etype == "ENGAGE":
            self._handle_engage(ts)
        elif etype == "DISENGAGE":
            self._handle_disengage(ts)
        elif etype == "STEERING_FORCE":
            if event.value is not None:
                self._handle_steering_force(ts, event.value)

    def _handle_engage(self, ts: float) -> None:
        """Transition from Disengaged to Engaged on driver request (FR-01)."""
        if self._state is State.DISENGAGED:
            self._transition(State.ENGAGED, ts, TRIGGER_ENGAGE)
            self._last_prompt_ts = ts
            self._awaiting_start_ts = None

    def _handle_disengage(self, ts: float) -> None:
        """Transition to Disengaged on driver request (FR-01)."""
        if self._state is not State.DISENGAGED:
            self._transition(State.DISENGAGED, ts, TRIGGER_DISENGAGE)
            self._last_prompt_ts = None
            self._awaiting_start_ts = None

    def _handle_steering_force(self, ts: float, force_n: float) -> None:
        """Apply FR-03 and FR-04 rules for a STEERING_FORCE event."""

        # FR-04: strictly greater than 10 N → immediate Disengaged override.
        if force_n > OVERRIDE_MIN_FORCE_N:
            self._transition(State.DISENGAGED, ts, TRIGGER_DRIVER_OVERRIDE)
            self._last_prompt_ts = None
            self._awaiting_start_ts = None
            return

        # FR-03: valid response is force ≤ 3 N.
        if force_n <= VALID_RESPONSE_MAX_FORCE_N:
            if self._state is State.AWAITING_RESPONSE:
                self._transition(State.ENGAGED, ts, TRIGGER_VALID_RESPONSE)
                self._last_prompt_ts = ts
                self._awaiting_start_ts = None
            elif self._state is State.ALARMING:
                self._transition(State.ENGAGED, ts, TRIGGER_VALID_RESPONSE)
                self._last_prompt_ts = ts

        # 3 N < force ≤ 10 N while awaiting response → ignored (FR-03).
        # No action needed for any other state combination.

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition(self, new_state: State, ts: float, trigger: str) -> None:
        """Record a state change and update internal state (FR-01).

        Same-state transitions are not recorded per FR-01.
        """
        if new_state is self._state:
            return
        self._writer.record_state_transition(
            timestamp=ts,
            previous=self._state.value,
            current=new_state.value,
            trigger=trigger,
        )
        self._state = new_state
