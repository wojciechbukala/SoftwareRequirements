"""Actuator layer: constructs electronic commands for vehicle actuators."""

from dataclasses import dataclass


# Canonical actuator identifiers
BRAKING_SYSTEM = "BrakingSystem"
STEERING_MOTOR = "SteeringMotor"
SPEED_ACTUATOR = "SpeedActuator"
STEERING_WHEEL = "SteeringWheel"
ALARM_ACTUATOR = "Alarm"


@dataclass
class ActuatorCommand:
    """An electronic instruction issued to a specific vehicle actuator."""
    timestamp_raw: str
    actuator_id: str
    values: str


def brake_command(timestamp_raw: str) -> ActuatorCommand:
    """Full emergency brake command sent to the braking system."""
    return ActuatorCommand(timestamp_raw, BRAKING_SYSTEM, "FULL_BRAKE")


def lane_keeping_command(timestamp_raw: str, correction: float) -> ActuatorCommand:
    """Steering correction command sent to the steering motor."""
    return ActuatorCommand(timestamp_raw, STEERING_MOTOR, f"{correction:.4f}")


def cruise_control_command(timestamp_raw: str, adjustment: float) -> ActuatorCommand:
    """Speed adjustment command sent to the speed actuator."""
    return ActuatorCommand(timestamp_raw, SPEED_ACTUATOR, f"{adjustment:.4f}")


def attentiveness_prompt_command(timestamp_raw: str) -> ActuatorCommand:
    """Small steering wheel nudge command that prompts the driver for a response."""
    return ActuatorCommand(timestamp_raw, STEERING_WHEEL, "ATTENTIVENESS_PROMPT")


def alarm_command(timestamp_raw: str) -> ActuatorCommand:
    """Continuous alarm command emitted when driver attentiveness check times out."""
    return ActuatorCommand(timestamp_raw, ALARM_ACTUATOR, "CONTINUOUS_ALARM")
