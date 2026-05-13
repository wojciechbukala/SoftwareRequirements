"""
Data models for the Copilot ADAS simulation system.

Defines enumerations, threshold constants, and data classes that represent
the system's state, events, and log entries.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ---------------------------------------------------------------------------
# Threshold constants (from the formal Alloy specification)
# ---------------------------------------------------------------------------

LIDAR_DANGER: int = 5          # Obstacle distance below which emergency braking triggers
OVERRIDE_FORCE: int = 10       # Steering force above which manual override is detected
VALID_RESPONSE_FORCE: int = 3  # Steering force at or below which a driver response is accepted
PROMPT_INTERVAL: int = 120     # Time units between attentiveness prompts
RESPONSE_WINDOW: int = 5       # Time units the driver has to respond before alarm escalation


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class State(Enum):
    """Autonomous-driving system states."""
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"


class SensorType(Enum):
    """Supported sensor kinds."""
    LIDAR = "Lidar"
    CAMERA = "Camera"


class DriverEventType(Enum):
    """Driver-initiated event kinds."""
    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"


class Actuator(Enum):
    """Physical actuators the system can command."""
    BRAKING_SYSTEM = "BrakingSystem"
    STEERING_MOTOR = "SteeringMotor"
    SPEED_ACTUATOR = "SpeedActuator"
    ALARM_ACTUATOR = "AlarmActuator"


class Feature(Enum):
    """Autonomous driving features that produce decisions."""
    EMERGENCY_BRAKING = "EmergencyBraking"
    LANE_KEEPING = "LaneKeeping"
    CRUISE_CONTROL = "CruiseControl"


class DecisionValue(Enum):
    """Possible outcomes of a feature decision."""
    BRAKE = "BRAKE"
    NO_BRAKE = "NO_BRAKE"
    ADJUST = "ADJUST"


# ---------------------------------------------------------------------------
# Input event data classes
# ---------------------------------------------------------------------------

@dataclass
class SensorEvent:
    """A periodic reading from one physical sensor."""
    timestamp: int
    sensor_id: str
    sensor_type: SensorType
    data_value: float
    unit: str


@dataclass
class DriverEvent:
    """An event initiated by the human driver."""
    timestamp: int
    event_type: DriverEventType
    value: Optional[float]  # steering force for STEERING_FORCE events; None otherwise


# ---------------------------------------------------------------------------
# Output log entry data classes
# ---------------------------------------------------------------------------

@dataclass
class StateLogEntry:
    """Records a single state-machine transition."""
    timestamp: int
    previous_state: State
    current_state: State
    trigger_event: str


@dataclass
class CommandEntry:
    """Records a single command issued to an actuator."""
    timestamp: int
    actuator_id: Actuator
    values: str


@dataclass
class FeatureDecisionEntry:
    """Records the output of one autonomous-feature evaluation."""
    timestamp: int
    feature: Feature
    decision: DecisionValue


# ---------------------------------------------------------------------------
# Mutable simulation state (used internally by the engine)
# ---------------------------------------------------------------------------

@dataclass
class SystemState:
    """
    Complete mutable state of the Copilot simulation at any point in time.

    Mirrors the SystemState signature from the Alloy model and is mutated
    in-place as events are processed.
    """
    current_state: State = State.DISENGAGED
    last_prompt: int = 0      # Timestamp of last successful attentiveness confirmation
    awaiting_since: int = 0   # Timestamp when the system entered AwaitingResponse

    state_log: List[StateLogEntry] = field(default_factory=list)
    commands_log: List[CommandEntry] = field(default_factory=list)
    feature_decision_log: List[FeatureDecisionEntry] = field(default_factory=list)
