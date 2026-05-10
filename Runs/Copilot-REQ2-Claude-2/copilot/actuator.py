"""Actuator control layer: constructs electronic commands for vehicle actuators."""

from .models import ActuatorCommand

# Actuator identifiers
ACTUATOR_BRAKING_SYSTEM = "braking_system"
ACTUATOR_STEERING_MOTOR = "steering_motor"
ACTUATOR_SPEED = "speed_actuator"
ACTUATOR_STEERING_WHEEL = "steering_wheel_actuator"
ACTUATOR_ALARM = "alarm_actuator"

# Command value constants
CMD_BRAKE = "BRAKE"
CMD_PROMPT = "PROMPT"
CMD_ALARM = "ALARM"


def brake_command(timestamp: float) -> ActuatorCommand:
    """Issue an emergency braking command to the braking system."""
    return ActuatorCommand(timestamp=timestamp, actuator_id=ACTUATOR_BRAKING_SYSTEM, values=CMD_BRAKE)


def lane_keeping_command(timestamp: float, correction: float) -> ActuatorCommand:
    """Issue a lane-keeping steering correction to the steering motor."""
    return ActuatorCommand(timestamp=timestamp, actuator_id=ACTUATOR_STEERING_MOTOR, values=correction)


def cruise_control_command(timestamp: float, adjustment: float) -> ActuatorCommand:
    """Issue a cruise-control speed adjustment to the speed actuator."""
    return ActuatorCommand(timestamp=timestamp, actuator_id=ACTUATOR_SPEED, values=adjustment)


def attentiveness_prompt_command(timestamp: float) -> ActuatorCommand:
    """Issue a small steering-wheel movement to prompt the driver for attention."""
    return ActuatorCommand(timestamp=timestamp, actuator_id=ACTUATOR_STEERING_WHEEL, values=CMD_PROMPT)


def alarm_command(timestamp: float) -> ActuatorCommand:
    """Issue a continuous alarm command to the alarm actuator."""
    return ActuatorCommand(timestamp=timestamp, actuator_id=ACTUATOR_ALARM, values=CMD_ALARM)
