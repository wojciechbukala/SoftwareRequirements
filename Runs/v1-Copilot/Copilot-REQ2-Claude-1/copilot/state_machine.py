"""State machine: manages Copilot operating modes and processes all events.

States (FR-01):
  Disengaged      - autonomous features inactive; emergency braking still active.
  Engaged         - full autonomous operation; attentiveness timer running.
  AwaitingResponse- system waiting up to 5 s for driver confirmation (FR-03).
  Alarming        - driver did not respond; continuous alarm active (FR-03).
"""

from enum import Enum
from typing import Optional

from copilot import actuator as act
from copilot import decision as dec
from copilot.output import OutputWriter
from copilot.perception import DriverEvent, SensorEvent


class State(Enum):
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"


# Timing thresholds (seconds)
ATTENTIVENESS_INTERVAL = 120.0
RESPONSE_WINDOW = 5.0

# Steering force thresholds (Newtons)
VALID_RESPONSE_FORCE_MAX = 3.0   # ≤ 3 N is a valid attentiveness response
OVERRIDE_FORCE_MIN = 10.0         # > 10 N triggers immediate disengagement (FR-04)


class StateMachine:
    """Processes the merged event stream, enforces state transitions, and drives output."""

    def __init__(self, writer: OutputWriter) -> None:
        self._state = State.DISENGAGED
        self._writer = writer

        # Tracks when the 120-second attentiveness interval started
        self._last_prompt_at: Optional[float] = None
        # Tracks when AwaitingResponse was entered (for 5-second timeout)
        self._awaiting_since: Optional[float] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process_event(self, kind: str, event) -> None:
        """Dispatch one event from the merged stream to the appropriate handler."""
        if kind == "sensor":
            self._handle_sensor(event)
        else:
            self._handle_driver(event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition(self, new_state: State, timestamp_raw: str, trigger: str) -> None:
        """Apply a state change and write a record to state_log.csv."""
        self._writer.write_state_transition(
            timestamp_raw,
            self._state.value,
            new_state.value,
            trigger,
        )
        print(f"  [state] {self._state.value} -> {new_state.value}  trigger={trigger}")
        self._state = new_state

    def _check_time_based_transitions(self, current_time: float, timestamp_raw: str) -> None:
        """Fire any time-driven transitions that are due before processing the current event.

        Two checks are performed in priority order:
        1. If Engaged and 120 s have elapsed since the last prompt, issue the
           attentiveness prompt and move to AwaitingResponse.
        2. If AwaitingResponse and the 5-second window has expired, move to Alarming.
        """
        if (
            self._state == State.ENGAGED
            and self._last_prompt_at is not None
            and current_time - self._last_prompt_at >= ATTENTIVENESS_INTERVAL
        ):
            prompt_cmd = act.attentiveness_prompt_command(timestamp_raw)
            self._writer.write_command(prompt_cmd)
            self._transition(State.AWAITING_RESPONSE, timestamp_raw, "ATTENTIVENESS_PROMPT")
            self._awaiting_since = current_time
            return  # re-check on next event

        if (
            self._state == State.AWAITING_RESPONSE
            and self._awaiting_since is not None
            and current_time - self._awaiting_since > RESPONSE_WINDOW
        ):
            alarm_cmd = act.alarm_command(timestamp_raw)
            self._writer.write_command(alarm_cmd)
            self._transition(State.ALARMING, timestamp_raw, "RESPONSE_TIMEOUT")
            self._awaiting_since = None

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_sensor(self, event: SensorEvent) -> None:
        """Process one sensor event according to PF-01."""
        self._check_time_based_transitions(event.timestamp, event.timestamp_raw)

        if event.sensor_type == "lidar":
            self._process_lidar(event)
        elif event.sensor_type == "camera":
            self._process_camera(event)

    def _process_lidar(self, event: SensorEvent) -> None:
        """Evaluate emergency braking for a Lidar reading (always active, FR-02 / PF-01)."""
        decision, command = dec.evaluate_emergency_braking(event)
        self._writer.write_decision(decision)
        if command:
            self._writer.write_command(command)
            print(f"  [emergency] BRAKE  distance={event.data_value}{event.unit}  t={event.timestamp_raw}")

    def _process_camera(self, event: SensorEvent) -> None:
        """Evaluate lane keeping and cruise control from a camera reading (Engaged only, PF-01)."""
        if self._state != State.ENGAGED:
            return

        lk_decision, lk_command = dec.evaluate_lane_keeping(event)
        cc_decision, cc_command = dec.evaluate_cruise_control(event)

        # Emergency braking takes precedence; camera produces no braking decision,
        # so both features are always recorded together when in Engaged mode.
        self._writer.write_decision(lk_decision)
        self._writer.write_decision(cc_decision)
        self._writer.write_command(lk_command)
        self._writer.write_command(cc_command)

    def _handle_driver(self, event: DriverEvent) -> None:
        """Process one driver event (FR-01, FR-03, FR-04)."""
        self._check_time_based_transitions(event.timestamp, event.timestamp_raw)

        if event.event_type == "ENGAGE":
            self._handle_engage(event)
        elif event.event_type == "DISENGAGE":
            self._handle_disengage(event)
        elif event.event_type == "STEERING_FORCE":
            self._handle_steering_force(float(event.value), event.timestamp, event.timestamp_raw)

    def _handle_engage(self, event: DriverEvent) -> None:
        """Transition from Disengaged to Engaged when the driver requests engagement."""
        if self._state == State.DISENGAGED:
            self._transition(State.ENGAGED, event.timestamp_raw, "ENGAGE")
            self._last_prompt_at = event.timestamp
        # Ignored if already in any engaged variant

    def _handle_disengage(self, event: DriverEvent) -> None:
        """Transition to Disengaged when the driver explicitly requests disengagement."""
        if self._state != State.DISENGAGED:
            self._transition(State.DISENGAGED, event.timestamp_raw, "DISENGAGE")
            self._last_prompt_at = None
            self._awaiting_since = None

    def _handle_steering_force(
        self, force: float, timestamp: float, timestamp_raw: str
    ) -> None:
        """Apply steering force logic for FR-03 (attentiveness) and FR-04 (override).

        Force thresholds:
          force > 10 N  → immediate disengage (FR-04), regardless of state
          force ≤ 3 N   → valid attentiveness response (AwaitingResponse / Alarming)
          3 N < force < 10 N → ignored while AwaitingResponse; no-op otherwise
        """
        # FR-04: driver override – highest priority
        if force > OVERRIDE_FORCE_MIN:
            self._transition(State.DISENGAGED, timestamp_raw, "STEERING_OVERRIDE")
            self._last_prompt_at = None
            self._awaiting_since = None
            return

        if self._state == State.AWAITING_RESPONSE:
            if force <= VALID_RESPONSE_FORCE_MAX:
                # Valid response: resume Engaged and reset the 120-second timer
                self._transition(State.ENGAGED, timestamp_raw, "VALID_RESPONSE")
                self._last_prompt_at = timestamp
                self._awaiting_since = None
            # 3 N < force ≤ 10 N: ignored per FR-03

        elif self._state == State.ALARMING:
            if force <= VALID_RESPONSE_FORCE_MAX:
                # Driver has re-engaged attention; return to Engaged
                self._transition(State.ENGAGED, timestamp_raw, "ALARM_CLEARED")
                self._last_prompt_at = timestamp
