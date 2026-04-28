"""
Actuator control layer: constructs electronic commands dispatched to vehicle actuators (SP5).

Actuators:
  BrakingSystem  – applies the vehicle brakes.
  SteeringMotor  – adjusts steering angle and issues attentiveness prompts (SP6).
  SpeedActuator  – controls vehicle speed.
  Alarm          – emits a continuous alarm sound (SP7).
"""

from dataclasses import dataclass

# Canonical actuator identifiers used in commands_log.csv
ACTUATOR_BRAKING_SYSTEM: str = "BrakingSystem"
ACTUATOR_STEERING_MOTOR: str = "SteeringMotor"
ACTUATOR_SPEED_ACTUATOR: str = "SpeedActuator"
ACTUATOR_ALARM: str = "Alarm"


@dataclass(frozen=True)
class ActuatorCommand:
    """An electronic instruction sent to one of the vehicle's actuators (SP5)."""

    timestamp: float
    actuator_id: str
    values: str


def emergency_brake_command(timestamp: float) -> ActuatorCommand:
    """Command the braking system to apply maximum emergency braking."""
    return ActuatorCommand(timestamp, ACTUATOR_BRAKING_SYSTEM, "EMERGENCY_BRAKE")


def lane_keep_command(timestamp: float, correction: float) -> ActuatorCommand:
    """Command the steering motor to apply a lane-keeping correction."""
    return ActuatorCommand(timestamp, ACTUATOR_STEERING_MOTOR, f"LANE_KEEP:{correction:.4f}")


def speed_adjust_command(timestamp: float, adjustment: float) -> ActuatorCommand:
    """Command the speed actuator to apply a cruise-control adjustment."""
    return ActuatorCommand(timestamp, ACTUATOR_SPEED_ACTUATOR, f"SPEED_ADJUST:{adjustment:.4f}")


def attentiveness_prompt_command(timestamp: float) -> ActuatorCommand:
    """Issue a small steering-wheel movement to prompt the driver for a response (SP6)."""
    return ActuatorCommand(timestamp, ACTUATOR_STEERING_MOTOR, "ATTENTIVENESS_PROMPT")


def alarm_command(timestamp: float) -> ActuatorCommand:
    """Activate the continuous alarm to alert an inattentive driver (SP7)."""
    return ActuatorCommand(timestamp, ACTUATOR_ALARM, "CONTINUOUS_ALARM")
