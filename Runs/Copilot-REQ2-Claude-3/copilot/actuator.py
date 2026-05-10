"""
Actuator control layer — command construction.

This module is the boundary between the decision layer and the physical
actuators (or their simulation counterparts).  Every function here produces
an :class:`ActuatorCommand` that will be written to *commands_log.csv*.

Actuator IDs used in this system
---------------------------------
* ``BrakingSystem``  — emergency braking.
* ``SteeringMotor``  — lane-keeping lateral correction.
* ``SpeedActuator``  — cruise-control longitudinal adjustment.
* ``SteeringWheel``  — haptic/vibratory attentiveness prompt.
* ``Alarm``          — audible/visual driver alarm.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


# ---------------------------------------------------------------------------
# ActuatorCommand dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ActuatorCommand:
    """
    A command dispatched to a specific actuator.

    Attributes:
        timestamp:   When the command should be applied (event timestamp).
        actuator_id: Identifier of the target actuator subsystem.
        values:      Command payload — either a string directive or a numeric
                     setpoint.
    """

    timestamp: float
    actuator_id: str
    values: Union[str, float]


# ---------------------------------------------------------------------------
# Command factory functions
# ---------------------------------------------------------------------------

def brake_command(timestamp: float) -> ActuatorCommand:
    """
    Build an emergency-braking command for the braking system.

    Args:
        timestamp: Timestamp at which the command is issued.

    Returns:
        :class:`ActuatorCommand` targeting ``BrakingSystem`` with value
        ``"BRAKE"``.
    """
    return ActuatorCommand(timestamp=timestamp, actuator_id="BrakingSystem", values="BRAKE")


def steer_command(timestamp: float, correction: float) -> ActuatorCommand:
    """
    Build a lane-keeping steering correction command.

    Args:
        timestamp:  Timestamp at which the command is issued.
        correction: Lateral correction setpoint derived from camera data.

    Returns:
        :class:`ActuatorCommand` targeting ``SteeringMotor``.
    """
    return ActuatorCommand(timestamp=timestamp, actuator_id="SteeringMotor", values=correction)


def speed_command(timestamp: float, adjustment: float) -> ActuatorCommand:
    """
    Build a cruise-control speed adjustment command.

    Args:
        timestamp:  Timestamp at which the command is issued.
        adjustment: Longitudinal adjustment setpoint derived from camera data.

    Returns:
        :class:`ActuatorCommand` targeting ``SpeedActuator``.
    """
    return ActuatorCommand(timestamp=timestamp, actuator_id="SpeedActuator", values=adjustment)


def prompt_command(timestamp: float) -> ActuatorCommand:
    """
    Build an attentiveness prompt command sent to the steering wheel.

    Issued every 120 s while the system is in the Engaged state as a subtle
    haptic nudge to confirm the driver is present.

    Args:
        timestamp: Timestamp at which the command is issued.

    Returns:
        :class:`ActuatorCommand` targeting ``SteeringWheel`` with value
        ``"small_movement"``.
    """
    return ActuatorCommand(timestamp=timestamp, actuator_id="SteeringWheel", values="small_movement")


def alarm_command(timestamp: float) -> ActuatorCommand:
    """
    Build a continuous alarm command issued when the driver fails to respond.

    Triggered when the system transitions from AwaitingResponse to Alarming
    after the 5-second response timeout expires.

    Args:
        timestamp: Timestamp at which the command is issued.

    Returns:
        :class:`ActuatorCommand` targeting ``Alarm`` with value
        ``"continuous_alarm"``.
    """
    return ActuatorCommand(timestamp=timestamp, actuator_id="Alarm", values="continuous_alarm")
