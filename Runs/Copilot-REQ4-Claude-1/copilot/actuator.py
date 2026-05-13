"""Actuator control layer: translate decisions into actuator commands."""

from .models import CommandEntry


def command_brake(timestamp: float) -> CommandEntry:
    """Issue an emergency brake command to the BrakingSystem actuator."""
    return CommandEntry(timestamp=timestamp, actuator_id="BrakingSystem", values="BRAKE")


def command_steering_adjust(timestamp: float) -> CommandEntry:
    """Issue a lane-keeping adjustment command to the SteeringMotor actuator."""
    return CommandEntry(timestamp=timestamp, actuator_id="SteeringMotor", values="ADJUST")


def command_speed_adjust(timestamp: float) -> CommandEntry:
    """Issue a cruise-control adjustment command to the SpeedActuator actuator."""
    return CommandEntry(timestamp=timestamp, actuator_id="SpeedActuator", values="ADJUST")


def command_attentiveness_prompt(timestamp: float) -> CommandEntry:
    """Issue an attentiveness-check prompt via the SteeringMotor actuator."""
    return CommandEntry(timestamp=timestamp, actuator_id="SteeringMotor", values="PROMPT")


def command_alarm(timestamp: float) -> CommandEntry:
    """Issue an alarm command to the AlarmActuator actuator."""
    return CommandEntry(timestamp=timestamp, actuator_id="AlarmActuator", values="ALARM")
