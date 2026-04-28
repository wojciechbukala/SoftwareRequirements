"""Actuator control layer: named actuator IDs and command value builders."""

# Canonical actuator identifiers
BRAKING_SYSTEM = "BrakingSystem"
STEERING_MOTOR = "SteeringMotor"
SPEED_ACTUATOR = "SpeedActuator"
ALARM_ACTUATOR = "AlarmActuator"


def brake_command() -> str:
    """Command value sent to BrakingSystem during emergency braking."""
    return "EMERGENCY_BRAKE"


def attentiveness_prompt_command() -> str:
    """Command value sent to SteeringMotor to prompt driver attentiveness (SP6)."""
    return "ATTENTIVENESS_PROMPT"


def lane_correction_command(correction: float) -> str:
    """Command value sent to SteeringMotor for lane keeping correction."""
    return f"lane_correction={correction}"


def speed_adjustment_command(adjustment: float) -> str:
    """Command value sent to SpeedActuator for cruise control adjustment."""
    return f"speed_adjustment={adjustment}"


def continuous_alarm_command() -> str:
    """Command value sent to AlarmActuator when driver attentiveness check fails (SP7)."""
    return "CONTINUOUS_ALARM"
