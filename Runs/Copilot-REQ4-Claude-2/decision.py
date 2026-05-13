"""
Decision layer — state machine implementing Copilot autonomous-driving logic.

States: Disengaged, Engaged, AwaitingResponse, Alarming.

Key thresholds (mirrors the Alloy model constants):
  LIDAR_DANGER        =  5.0  m  — obstacle closer than this triggers emergency braking
  OVERRIDE_FORCE      = 10.0  N  — steering force above this is a manual override
  VALID_RESPONSE_FORCE =  3.0  N  — steering force at or below this confirms driver attention
  PROMPT_INTERVAL     = 120.0  s  — gap between attentiveness prompts
  RESPONSE_WINDOW     =   5.0  s  — time the driver has to respond before alarm escalates
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional

from perception import SensorEvent, DriverEvent, Event

# ---------------------------------------------------------------------------
# Threshold constants
# ---------------------------------------------------------------------------
LIDAR_DANGER = 5.0
OVERRIDE_FORCE = 10.0
VALID_RESPONSE_FORCE = 3.0
PROMPT_INTERVAL = 120.0   # seconds
RESPONSE_WINDOW = 5.0     # seconds

# ---------------------------------------------------------------------------
# Output record types
# ---------------------------------------------------------------------------

@dataclass
class StateLogEntry:
    """Records a single state transition."""
    timestamp: float
    previous_state: str
    current_state: str
    trigger_event: str


@dataclass
class CommandEntry:
    """Records a command dispatched to an actuator."""
    timestamp: float
    actuator_id: str
    values: str


@dataclass
class FeatureDecisionEntry:
    """Records an autonomous feature decision."""
    timestamp: float
    feature: str
    decision: str


# ---------------------------------------------------------------------------
# Decision engine
# ---------------------------------------------------------------------------

class CopilotEngine:
    """
    Event-driven state machine for the Copilot ADAS.

    Call process(events) with a mixed list of SensorEvent and DriverEvent
    objects.  Outputs are accumulated in state_log, commands_log, and
    feature_decisions.
    """

    def __init__(self) -> None:
        self.state: str = 'Disengaged'
        self.last_prompt: float = 0.0    # timestamp of last attentiveness prompt
        self.awaiting_since: float = 0.0  # timestamp when AwaitingResponse began

        self.state_log: List[StateLogEntry] = []
        self.commands_log: List[CommandEntry] = []
        self.feature_decisions: List[FeatureDecisionEntry] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition(self, t: float, from_state: str, to_state: str, trigger: str) -> None:
        """Execute a state transition and record it."""
        self.state = to_state
        self.state_log.append(StateLogEntry(t, from_state, to_state, trigger))

    def _emit_command(self, t: float, actuator: str, values: str) -> None:
        """Dispatch a command to the actuator layer."""
        self.commands_log.append(CommandEntry(t, actuator, values))

    def _emit_feature_decision(self, t: float, feature: str, decision: str) -> None:
        """Record an autonomous feature decision."""
        self.feature_decisions.append(FeatureDecisionEntry(t, feature, decision))

    # ------------------------------------------------------------------
    # Internal (time-driven) steps
    # ------------------------------------------------------------------

    def _internal_step(self, t: float) -> None:
        """
        Evaluate time-based transitions for a single clock tick at time t.

        Only one transition fires per tick (matches Alloy elif semantics):
          1. Engaged long enough  ->  AwaitingResponse + prompt command
          2. Awaiting too long    ->  Alarming + alarm command
          3. Already Alarming     ->  repeat alarm command
        """
        if self.state == 'Engaged' and t >= self.last_prompt + PROMPT_INTERVAL:
            self._transition(t, 'Engaged', 'AwaitingResponse', 'PROMPT_CHECK')
            self.awaiting_since = t
            self._emit_command(t, 'SteeringMotor', 'prompt')

        elif self.state == 'AwaitingResponse' and t >= self.awaiting_since + RESPONSE_WINDOW:
            self._transition(t, 'AwaitingResponse', 'Alarming', 'RESPONSE_TIMEOUT')
            self._emit_command(t, 'AlarmActuator', 'alarm')

        elif self.state == 'Alarming':
            # One alarm command per clock tick while Alarming
            self._emit_command(t, 'AlarmActuator', 'alarm')

    def _run_internal_steps(self, from_time: float, to_time: float, include_to: bool = False) -> None:
        """
        Simulate internal ticks at each integer-second mark strictly between
        from_time and to_time.  When include_to is True the integer floor of
        to_time is included (used for the post-event continuation phase where
        no event fires at to_time).
        """
        start = math.floor(from_time) + 1
        if include_to:
            end = math.floor(to_time)
        else:
            # Exclude to_time when it falls exactly on an integer: an event
            # fires there, so no internal step should precede it at the same tick.
            end = int(to_time) - 1 if to_time == math.floor(to_time) else math.floor(to_time)
        for t_int in range(int(start), int(end) + 1):
            self._internal_step(float(t_int))

    # ------------------------------------------------------------------
    # Sensor event handlers (perception -> decision)
    # ------------------------------------------------------------------

    def _handle_lidar(self, event: SensorEvent) -> None:
        """Emergency braking decision based on Lidar distance reading."""
        t = event.timestamp
        if event.data_value < LIDAR_DANGER:
            self._emit_feature_decision(t, 'EmergencyBraking', 'BRAKE')
            self._emit_command(t, 'BrakingSystem', 'brake')
        else:
            self._emit_feature_decision(t, 'EmergencyBraking', 'NO_BRAKE')

    def _handle_camera(self, event: SensorEvent) -> None:
        """Lane keeping and cruise control decisions from camera data (Engaged only)."""
        t = event.timestamp
        if self.state == 'Engaged':
            self._emit_feature_decision(t, 'LaneKeeping', 'ADJUST')
            self._emit_feature_decision(t, 'CruiseControl', 'ADJUST')
            self._emit_command(t, 'SteeringMotor', 'adjust')
            self._emit_command(t, 'SpeedActuator', 'adjust')

    def _process_sensor_event(self, event: SensorEvent) -> None:
        """Dispatch a sensor event to the appropriate handler."""
        sensor_type = event.sensor_type
        if sensor_type == 'Lidar':
            self._handle_lidar(event)
        elif sensor_type == 'Camera':
            self._handle_camera(event)

    # ------------------------------------------------------------------
    # Driver event handlers
    # ------------------------------------------------------------------

    def _handle_engage(self, event: DriverEvent) -> None:
        """ENGAGE: Disengaged -> Engaged (no-op if already engaged)."""
        if self.state == 'Disengaged':
            self._transition(event.timestamp, 'Disengaged', 'Engaged', 'ENGAGE')
            self.last_prompt = event.timestamp

    def _handle_disengage(self, event: DriverEvent) -> None:
        """DISENGAGE: any active state -> Disengaged."""
        if self.state != 'Disengaged':
            self._transition(event.timestamp, self.state, 'Disengaged', 'DISENGAGE')

    def _handle_steering_force(self, event: DriverEvent) -> None:
        """
        STEERING_FORCE:
          force > OVERRIDE_FORCE                    -> Disengaged (manual override)
          force <= VALID_RESPONSE_FORCE & Awaiting  -> Engaged (valid attentiveness response)
          force <= VALID_RESPONSE_FORCE & Alarming  -> Engaged (alarm escape)
          mid-range force & AwaitingResponse        -> no-op (ignored, keep waiting)
          all other cases                           -> no-op
        """
        t = event.timestamp
        force = event.value if event.value is not None else 0.0

        if force > OVERRIDE_FORCE:
            if self.state != 'Disengaged':
                self._transition(t, self.state, 'Disengaged', 'STEERING_FORCE')

        elif force <= VALID_RESPONSE_FORCE:
            if self.state == 'AwaitingResponse':
                self._transition(t, 'AwaitingResponse', 'Engaged', 'STEERING_FORCE')
                self.last_prompt = t
            elif self.state == 'Alarming':
                self._transition(t, 'Alarming', 'Engaged', 'STEERING_FORCE')
                self.last_prompt = t

        # Mid-range force (VALID_RESPONSE_FORCE < force <= OVERRIDE_FORCE):
        # While AwaitingResponse this is an insufficient response — system keeps waiting.
        # In all other states it is silently ignored.

    def _process_driver_event(self, event: DriverEvent) -> None:
        """Dispatch a driver event to the appropriate handler."""
        if event.event_type == 'ENGAGE':
            self._handle_engage(event)
        elif event.event_type == 'DISENGAGE':
            self._handle_disengage(event)
        elif event.event_type == 'STEERING_FORCE':
            self._handle_steering_force(event)

    # ------------------------------------------------------------------
    # Main processing loop
    # ------------------------------------------------------------------

    def process(self, events: List[Event]) -> None:
        """
        Process all events in chronological order.

        For each consecutive pair of event timestamps, internal clock ticks
        are simulated at integer-second marks so that time-based transitions
        (attentiveness prompts, response timeouts, alarm ticks) fire correctly.
        After the final event, if the system is still Alarming the alarm
        continues for one additional RESPONSE_WINDOW period.
        """
        sorted_events = sorted(events, key=lambda e: e.timestamp)

        prev_time: float = 0.0
        for event in sorted_events:
            self._run_internal_steps(prev_time, event.timestamp)

            if isinstance(event, SensorEvent):
                self._process_sensor_event(event)
            else:
                self._process_driver_event(event)

            prev_time = event.timestamp

        # If the system ends in an active time-sensitive state, continue ticking
        # so that pending alarms are fully reflected in the output.
        if self.state in ('Alarming', 'AwaitingResponse'):
            self._run_internal_steps(prev_time, prev_time + RESPONSE_WINDOW, include_to=True)
