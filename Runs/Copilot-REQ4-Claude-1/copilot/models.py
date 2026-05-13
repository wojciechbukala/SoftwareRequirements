"""Data models for the Copilot ADAS simulation."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class State(str, Enum):
    """Autonomous system operating states."""

    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"


class SensorType(str, Enum):
    """Supported sensor modalities."""

    LIDAR = "Lidar"
    CAMERA = "Camera"


class DriverEventType(str, Enum):
    """Types of driver-initiated events."""

    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"


@dataclass
class SensorEvent:
    """A single reading from a vehicle sensor."""

    timestamp: float
    sensor_id: str
    sensor_type: SensorType
    data_value: float
    unit: str


@dataclass
class DriverEvent:
    """A driver action delivered to the system."""

    timestamp: float
    event_type: DriverEventType
    value: Optional[float]  # only set for STEERING_FORCE events


@dataclass
class StateLogEntry:
    """Record of one state-machine transition."""

    timestamp: float
    previous_state: str
    current_state: str
    trigger_event: str


@dataclass
class CommandEntry:
    """A command issued to a physical actuator."""

    timestamp: float
    actuator_id: str
    values: str


@dataclass
class FeatureDecisionEntry:
    """The output of one ADAS feature for a given sensor reading."""

    timestamp: float
    feature: str
    decision: str
