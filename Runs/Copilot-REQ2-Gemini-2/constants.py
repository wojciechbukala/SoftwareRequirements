from enum import Enum

# System States (FR-01)
class SystemState(Enum):
    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"

# Sensor Types (Design Constraints)
class SensorType(Enum):
    LIDAR = "LIDAR"
    CAMERA = "CAMERA"

# Driver Event Types (Design Constraints)
class DriverEventType(Enum):
    ENGAGE = "ENGAGE"
    DISENGAGE = "DISENGAGE"
    STEERING_FORCE = "STEERING_FORCE"

# Actuator IDs (Derived from FR-02, FR-03)
class ActuatorID(Enum):
    BRAKING_SYSTEM = "BrakingSystem"
    STEERING_MOTOR = "SteeringMotor"
    ALARM = "Alarm"

# Autonomous Features (FR-02)
class Feature(Enum):
    EMERGENCY_BRAKING = "EmergencyBraking"
    LANE_KEEPING = "LaneKeeping"
    CRUISE_CONTROL = "CruiseControl"

# Thresholds and Intervals
EMERGENCY_BRAKING_DISTANCE_M = 5.0  # meters (FR-02)
ATTENTIVENESS_PROMPT_INTERVAL_S = 120.0  # seconds (FR-03)
ATTENTIVENESS_RESPONSE_WINDOW_S = 5.0  # seconds (FR-03)
ATTENTIVENESS_VALID_RESPONSE_FORCE_N = 3.0  # Newtons (FR-03)
DRIVER_OVERRIDE_FORCE_N = 10.0  # Newtons (FR-04)

# CSV Headers (Design Constraints)
SENSOR_LOG_HEADERS = ["timestamp", "sensor_id", "sensor_type", "data_value", "unit"]
DRIVER_EVENTS_HEADERS = ["timestamp", "event_type", "value"]

STATE_LOG_HEADERS = ["timestamp", "previous_state", "current_state", "trigger_event"]
COMMANDS_LOG_HEADERS = ["timestamp", "actuator_id", "values"]
FEATURE_DECISION_HEADERS = ["timestamp", "feature", "decision"]
