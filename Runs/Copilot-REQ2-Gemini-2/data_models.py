from dataclasses import dataclass, field
from functools import total_ordering
from typing import Union, Optional

from constants import SensorType, DriverEventType, SystemState, ActuatorID, Feature

@dataclass
class SensorEvent:
    timestamp: float
    sensor_id: str
    sensor_type: SensorType
    data_value: float
    unit: str

@dataclass
class DriverEvent:
    timestamp: float
    event_type: DriverEventType
    value: Union[float, str] # Value can be a float for STEERING_FORCE or string for ENGAGE/DISENGAGE

@total_ordering
@dataclass
class MergedEvent:
    timestamp: float
    event_type: str # "sensor" or "driver"
    data: Union[SensorEvent, DriverEvent]

    def __lt__(self, other):
        if not isinstance(other, MergedEvent):
            return NotImplemented
        return self.timestamp < other.timestamp

    def __eq__(self, other):
        if not isinstance(other, MergedEvent):
            return NotImplemented
        return self.timestamp == other.timestamp and self.event_type == other.event_type and self.data == other.data

@dataclass
class StateLogEntry:
    timestamp: float
    previous_state: SystemState
    current_state: SystemState
    trigger_event: str # Description of the event that triggered the state change

@dataclass
class CommandLogEntry:
    timestamp: float
    actuator_id: ActuatorID
    value: Union[float, str] # e.g., brake force, steering angle, alarm status

@dataclass
class FeatureDecisionEntry:
    timestamp: float
    feature: Feature
    decision: Union[float, str] # e.g., "braking", "non-braking", steering adjustment, speed adjustment
