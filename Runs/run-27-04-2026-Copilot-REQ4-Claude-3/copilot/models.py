"""Domain models for the Copilot ADAS simulation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class State(Enum):
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"


class SensorType(Enum):
    LIDAR = "Lidar"
    CAMERA = "Camera"


class DriverEventType(Enum):
    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"


class ActuatorId(Enum):
    BRAKING_SYSTEM = "BrakingSystem"
    STEERING_MOTOR = "SteeringMotor"
    SPEED_ACTUATOR = "SpeedActuator"
    ALARM_ACTUATOR = "AlarmActuator"


class Feature(Enum):
    EMERGENCY_BRAKING = "EmergencyBraking"
    LANE_KEEPING = "LaneKeeping"
    CRUISE_CONTROL = "CruiseControl"


class Decision(Enum):
    BRAKE = "BRAKE"
    NO_BRAKE = "NO_BRAKE"
    ADJUST = "ADJUST"


@dataclass
class SensorEvent:
    """A reading from a physical sensor."""
    timestamp: int
    sensor_id: str
    sensor_type: SensorType
    data_value: float
    unit: str


@dataclass
class DriverEvent:
    """An intentional input from the driver."""
    timestamp: int
    event_type: DriverEventType
    value: Optional[float]  # Force in Newtons for STEERING_FORCE; None otherwise


@dataclass
class StateLogEntry:
    """Records a state transition."""
    timestamp: int
    previous_state: State
    current_state: State
    trigger_event: str


@dataclass
class CommandEntry:
    """Records a command issued to an actuator."""
    timestamp: int
    actuator_id: ActuatorId
    values: str


@dataclass
class FeatureDecisionEntry:
    """Records a feature-level decision made by the decision layer."""
    timestamp: int
    feature: Feature
    decision: Decision
