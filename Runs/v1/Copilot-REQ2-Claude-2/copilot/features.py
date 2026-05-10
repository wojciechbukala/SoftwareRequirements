"""
Decision logic layer: evaluates autonomous driving features for each sensor reading.

Features (FR-02):
  EmergencyBraking  – triggered when Lidar reports an obstacle closer than 5 m.
  LaneKeeping       – steering correction derived from camera data.
  CruiseControl     – speed adjustment derived from camera data.
"""

from dataclasses import dataclass

# Obstacle distance that triggers emergency braking (exclusive upper bound).
EMERGENCY_BRAKE_THRESHOLD_M: float = 5.0


@dataclass(frozen=True)
class FeatureDecision:
    """The outcome of evaluating one autonomous feature for a given sensor reading (SP4)."""

    timestamp: float
    feature: str    # 'EmergencyBraking', 'LaneKeeping', or 'CruiseControl'
    decision: str   # human-readable outcome string


def evaluate_emergency_braking(timestamp: float, distance_m: float) -> FeatureDecision:
    """Decide whether to apply emergency braking based on Lidar distance.

    Returns a BRAKE decision when distance_m < EMERGENCY_BRAKE_THRESHOLD_M,
    and a NO_BRAKE decision otherwise.
    """
    if distance_m < EMERGENCY_BRAKE_THRESHOLD_M:
        return FeatureDecision(timestamp, "EmergencyBraking", "BRAKE")
    return FeatureDecision(timestamp, "EmergencyBraking", "NO_BRAKE")


def evaluate_lane_keeping(timestamp: float, camera_value: float) -> FeatureDecision:
    """Compute a lane-keeping steering correction from a camera reading.

    The camera data_value is treated as the measured lateral lane offset.
    """
    return FeatureDecision(timestamp, "LaneKeeping", f"CORRECTION:{camera_value:.4f}")


def evaluate_cruise_control(timestamp: float, camera_value: float) -> FeatureDecision:
    """Compute a cruise-control speed adjustment from a camera reading."""
    return FeatureDecision(timestamp, "CruiseControl", f"ADJUSTMENT:{camera_value:.4f}")
