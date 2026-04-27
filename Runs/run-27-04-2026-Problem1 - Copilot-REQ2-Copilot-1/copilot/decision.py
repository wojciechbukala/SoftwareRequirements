"""Decision logic: evaluates autonomous driving features for incoming sensor events."""

from dataclasses import dataclass
from typing import Optional, Tuple

from copilot import actuator as act
from copilot.actuator import ActuatorCommand
from copilot.perception import SensorEvent


# Feature name constants used in feature_decision.csv
FEATURE_EMERGENCY_BRAKING = "EmergencyBraking"
FEATURE_LANE_KEEPING = "LaneKeeping"
FEATURE_CRUISE_CONTROL = "CruiseControl"

# Lidar distance threshold triggering emergency braking (metres, exclusive)
EMERGENCY_BRAKE_THRESHOLD_M = 5.0


@dataclass
class FeatureDecision:
    """The outcome of evaluating one autonomous feature for a given sensor event."""
    timestamp_raw: str
    feature: str
    decision: str


def evaluate_emergency_braking(
    event: SensorEvent,
) -> Tuple[FeatureDecision, Optional[ActuatorCommand]]:
    """Evaluate emergency braking from a Lidar reading.

    Returns a FeatureDecision and, when braking is triggered, a braking
    ActuatorCommand.  The command is None when no braking is required.
    Distance strictly less than 5 m triggers braking (FR-02 / PF-01).
    """
    if event.data_value < EMERGENCY_BRAKE_THRESHOLD_M:
        decision = FeatureDecision(event.timestamp_raw, FEATURE_EMERGENCY_BRAKING, "BRAKE")
        command = act.brake_command(event.timestamp_raw)
        return decision, command

    decision = FeatureDecision(event.timestamp_raw, FEATURE_EMERGENCY_BRAKING, "NO_BRAKE")
    return decision, None


def evaluate_lane_keeping(
    event: SensorEvent,
) -> Tuple[FeatureDecision, ActuatorCommand]:
    """Compute a lane-keeping correction from a camera sensor reading.

    The data_value represents lateral deviation from the lane centre.  A
    proportional correction in the opposite direction is issued to the
    steering motor.
    """
    correction = -event.data_value
    decision = FeatureDecision(
        event.timestamp_raw,
        FEATURE_LANE_KEEPING,
        f"CORRECTION:{correction:.4f}",
    )
    command = act.lane_keeping_command(event.timestamp_raw, correction)
    return decision, command


def evaluate_cruise_control(
    event: SensorEvent,
) -> Tuple[FeatureDecision, ActuatorCommand]:
    """Compute a cruise-control speed adjustment from a camera sensor reading.

    The data_value is used as a proportional speed adjustment signal passed
    directly to the speed actuator.
    """
    adjustment = event.data_value
    decision = FeatureDecision(
        event.timestamp_raw,
        FEATURE_CRUISE_CONTROL,
        f"ADJUSTMENT:{adjustment:.4f}",
    )
    command = act.cruise_control_command(event.timestamp_raw, adjustment)
    return decision, command
