"""Data models for the Copilot driver-assistance system."""

from dataclasses import dataclass
from enum import Enum
from typing import Union


class State(Enum):
    """Operational states of the Copilot system."""
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"


@dataclass
class SensorEvent:
    """A single reading from an on-board sensor."""
    timestamp: float
    sensor_id: str
    sensor_type: str
    data_value: float
    unit: str


@dataclass
class DriverEvent:
    """A single interaction originating from the driver."""
    timestamp: float
    event_type: str   # ENGAGE | DISENGAGE | STEERING_FORCE
    value: float


@dataclass
class StateTransition:
    """Record of an actual state change in the system."""
    timestamp: float
    previous_state: str
    current_state: str
    trigger_event: str


@dataclass
class ActuatorCommand:
    """Electronic instruction sent to a vehicle actuator."""
    timestamp: float
    actuator_id: str
    values: Union[str, float]


@dataclass
class FeatureDecision:
    """Outcome of evaluating one autonomous feature for a given input."""
    timestamp: float
    feature: str
    decision: Union[str, float]
