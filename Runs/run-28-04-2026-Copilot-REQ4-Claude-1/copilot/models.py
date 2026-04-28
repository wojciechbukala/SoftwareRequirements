"""Domain model: enumerations and plain data-classes used across all layers."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class State(str, Enum):
    """Autonomous-driving state of the vehicle."""
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"


class SensorType(str, Enum):
    """Physical sensor kind."""
    LIDAR = "Lidar"
    CAMERA = "Camera"


class DriverEventType(str, Enum):
    """Types of driver-initiated events."""
    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"


class Feature(str, Enum):
    """Autonomous-driving feature that produces a decision."""
    EMERGENCY_BRAKING = "EmergencyBraking"
    LANE_KEEPING = "LaneKeeping"
    CRUISE_CONTROL = "CruiseControl"


class Decision(str, Enum):
    """Value of a feature decision."""
    BRAKE = "BRAKE"
    NO_BRAKE = "NO_BRAKE"
    ADJUST = "ADJUST"


class Actuator(str, Enum):
    """Physical actuator targeted by a command."""
    BRAKING_SYSTEM = "BrakingSystem"
    STEERING_MOTOR = "SteeringMotor"
    SPEED_ACTUATOR = "SpeedActuator"
    ALARM_ACTUATOR = "AlarmActuator"


# ---------------------------------------------------------------------------
# Input events
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SensorEvent:
    """One row of sensor_log.csv – a single sensor reading."""
    timestamp: int
    sensor_id: str
    sensor_type: SensorType
    data_value: float
    unit: str


@dataclass(frozen=True)
class DriverEvent:
    """One row of driver_events.csv – a driver-initiated action."""
    timestamp: int
    event_type: DriverEventType
    # Force value (N) is present only for STEERING_FORCE events (per Alloy model).
    value: Optional[float] = None


# ---------------------------------------------------------------------------
# Output records
# ---------------------------------------------------------------------------

@dataclass
class StateLogEntry:
    """One row of state_log.csv – a recorded state transition."""
    timestamp: int
    previous_state: State
    current_state: State
    trigger_event: str


@dataclass
class CommandEntry:
    """One row of commands_log.csv – an actuator command."""
    timestamp: int
    actuator_id: Actuator
    values: str = ""


@dataclass
class FeatureDecisionEntry:
    """One row of feature_decision.csv – a feature-level decision."""
    timestamp: int
    feature: Feature
    decision: Decision
