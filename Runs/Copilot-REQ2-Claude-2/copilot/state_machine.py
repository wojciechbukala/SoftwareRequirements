"""State machine: processes merged events and maintains runtime context."""

from dataclasses import dataclass, field
from typing import List, Optional, Union

from .models import (
    State, SensorEvent, DriverEvent,
    StateTransition, ActuatorCommand, FeatureDecision,
)
from .perception import analyse_lidar, analyse_camera
from .decision import (
    evaluate_emergency_braking, evaluate_lane_keeping, evaluate_cruise_control,
    DECISION_BRAKE,
)
from .actuator import (
    brake_command, lane_keeping_command, cruise_control_command,
    attentiveness_prompt_command, alarm_command,
)

# Timing constants (seconds)
ATTENTIVENESS_INTERVAL: float = 120.0
RESPONSE_WINDOW: float = 5.0

# Force thresholds (Newtons)
VALID_RESPONSE_MAX_FORCE: float = 3.0
OVERRIDE_FORCE_THRESHOLD: float = 10.0

# Trigger event label constants
TRIGGER_ENGAGE = "ENGAGE"
TRIGGER_DISENGAGE = "DISENGAGE"
TRIGGER_DRIVER_OVERRIDE = "DRIVER_OVERRIDE"
TRIGGER_ATTENTIVENESS_PROMPT = "ATTENTIVENESS_PROMPT"
TRIGGER_ATTENTIVENESS_RESPONSE = "ATTENTIVENESS_RESPONSE"
TRIGGER_ATTENTIVENESS_TIMEOUT = "ATTENTIVENESS_TIMEOUT"
TRIGGER_ALARM_CLEARED = "ALARM_CLEARED"


@dataclass
class CopilotContext:
    """Runtime context maintained by the Copilot system."""
    state: State = State.DISENGAGED
    # Timestamp at which the 120 s attentiveness timer was last reset
    last_prompt_reset_time: float = 0.0
    # Timestamp at which the most recent attentiveness prompt was issued
    prompt_issued_at: Optional[float] = None

    # Accumulated output records
    state_transitions: List[StateTransition] = field(default_factory=list)
    actuator_commands: List[ActuatorCommand] = field(default_factory=list)
    feature_decisions: List[FeatureDecision] = field(default_factory=list)


def _record_transition(ctx: CopilotContext, timestamp: float, new_state: State, trigger: str) -> None:
    """Record and apply a state transition when the state actually changes."""
    if ctx.state == new_state:
        return
    ctx.state_transitions.append(StateTransition(
        timestamp=timestamp,
        previous_state=ctx.state.value,
        current_state=new_state.value,
        trigger_event=trigger,
    ))
    ctx.state = new_state


def _check_time_based_transitions(ctx: CopilotContext, timestamp: float) -> None:
    """Fire time-driven transitions before processing the arriving event.

    Called at the start of every event dispatch so that elapsed-time conditions
    are evaluated against the current event's timestamp even when no dedicated
    timer event exists in the stream.
    """
    if ctx.state == State.ENGAGED:
        elapsed = timestamp - ctx.last_prompt_reset_time
        if elapsed >= ATTENTIVENESS_INTERVAL:
            # Issue attentiveness prompt and enter AwaitingResponse
            ctx.actuator_commands.append(attentiveness_prompt_command(timestamp))
            ctx.prompt_issued_at = timestamp
            _record_transition(ctx, timestamp, State.AWAITING_RESPONSE, TRIGGER_ATTENTIVENESS_PROMPT)

    if ctx.state == State.AWAITING_RESPONSE and ctx.prompt_issued_at is not None:
        if timestamp - ctx.prompt_issued_at > RESPONSE_WINDOW:
            # Response window expired – trigger alarm
            ctx.actuator_commands.append(alarm_command(timestamp))
            _record_transition(ctx, timestamp, State.ALARMING, TRIGGER_ATTENTIVENESS_TIMEOUT)


def _handle_sensor_event(ctx: CopilotContext, event: SensorEvent) -> None:
    """Process a single sensor event according to PF-01."""
    sensor_type = event.sensor_type.lower()

    if sensor_type == "lidar":
        # Emergency braking is evaluated regardless of operating mode (FR-02, PF-01)
        obs = analyse_lidar(event)
        decision = evaluate_emergency_braking(event.timestamp, obs)
        ctx.feature_decisions.append(decision)

        if obs.emergency_brake_required:
            ctx.actuator_commands.append(brake_command(event.timestamp))
            # Abandon further feature evaluation for this cycle (FR-02)
            return

    elif sensor_type == "camera":
        # Camera features are only active in Engaged mode (PF-01)
        if ctx.state != State.ENGAGED:
            return

        obs = analyse_camera(event)

        # Lane keeping
        lk_decision = evaluate_lane_keeping(event.timestamp, obs)
        ctx.feature_decisions.append(lk_decision)
        ctx.actuator_commands.append(lane_keeping_command(event.timestamp, obs.lane_keeping_correction))

        # Cruise control
        cc_decision = evaluate_cruise_control(event.timestamp, obs)
        ctx.feature_decisions.append(cc_decision)
        ctx.actuator_commands.append(cruise_control_command(event.timestamp, obs.cruise_control_adjustment))


def _handle_driver_event(ctx: CopilotContext, event: DriverEvent) -> None:
    """Process a single driver event according to FR-01, FR-03, and FR-04."""
    etype = event.event_type.upper()
    force = event.value

    if etype == "ENGAGE":
        if ctx.state == State.DISENGAGED:
            ctx.last_prompt_reset_time = event.timestamp
            _record_transition(ctx, event.timestamp, State.ENGAGED, TRIGGER_ENGAGE)

    elif etype == "DISENGAGE":
        if ctx.state != State.DISENGAGED:
            _record_transition(ctx, event.timestamp, State.DISENGAGED, TRIGGER_DISENGAGE)

    elif etype == "STEERING_FORCE":
        if force > OVERRIDE_FORCE_THRESHOLD:
            # Driver override: immediate transition to Disengaged (FR-04)
            _record_transition(ctx, event.timestamp, State.DISENGAGED, TRIGGER_DRIVER_OVERRIDE)
            return

        if force <= VALID_RESPONSE_MAX_FORCE:
            if ctx.state == State.AWAITING_RESPONSE:
                # Valid attentiveness response received
                ctx.last_prompt_reset_time = event.timestamp
                ctx.prompt_issued_at = None
                _record_transition(ctx, event.timestamp, State.ENGAGED, TRIGGER_ATTENTIVENESS_RESPONSE)
            elif ctx.state == State.ALARMING:
                # Driver clears the alarm by applying gentle force
                ctx.last_prompt_reset_time = event.timestamp
                ctx.prompt_issued_at = None
                _record_transition(ctx, event.timestamp, State.ENGAGED, TRIGGER_ALARM_CLEARED)
        # Force in (3N, 10N] while AwaitingResponse is explicitly ignored (FR-03)


def process_event(ctx: CopilotContext, event: Union[SensorEvent, DriverEvent]) -> None:
    """Dispatch a single event through the full processing pipeline."""
    _check_time_based_transitions(ctx, event.timestamp)

    if isinstance(event, SensorEvent):
        _handle_sensor_event(ctx, event)
    elif isinstance(event, DriverEvent):
        _handle_driver_event(ctx, event)


def run(events: List[Union[SensorEvent, DriverEvent]]) -> CopilotContext:
    """Execute the full event loop and return the populated runtime context."""
    ctx = CopilotContext()
    for event in events:
        process_event(ctx, event)
    return ctx
