from enum import Enum

# ---Enumerated domains---
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

class FeatureDecisionKind(Enum):
    EMERGENCY_BRAKING = "EmergencyBraking"
    LANE_KEEPING = "LaneKeeping"
    CRUISE_CONTROL = "CruiseControl"

class DecisionValue(Enum):
    BRAKE = "BRAKE"
    NO_BRAKE = "NO_BRAKE"
    ADJUST = "ADJUST"

class Actuator(Enum):
    BRAKING_SYSTEM = "BrakingSystem"
    STEERING_MOTOR = "SteeringMotor"
    SPEED_ACTUATOR = "SpeedActuator"
    ALARM_ACTUATOR = "AlarmActuator"

# ---Threshold constants---
LIDAR_DANGER = 5
OVERRIDE_FORCE = 10
VALID_RESPONSE_FORCE = 3
PROMPT_INTERVAL = 120
RESPONSE_WINDOW = 5
