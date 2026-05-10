"""Perception layer: interprets raw sensor readings into structured observations."""

from dataclasses import dataclass

from .models import SensorEvent

EMERGENCY_BRAKE_DISTANCE_THRESHOLD = 5.0  # metres (exclusive)


@dataclass
class LidarObservation:
    """Structured result of analysing a Lidar sensor reading."""
    distance: float
    emergency_brake_required: bool


@dataclass
class CameraObservation:
    """Structured result of analysing a camera sensor reading."""
    lane_keeping_correction: float
    cruise_control_adjustment: float


def analyse_lidar(event: SensorEvent) -> LidarObservation:
    """Interpret a Lidar sensor event.

    Emergency braking is required when the measured distance is strictly below
    the threshold defined in FR-02.
    """
    return LidarObservation(
        distance=event.data_value,
        emergency_brake_required=event.data_value < EMERGENCY_BRAKE_DISTANCE_THRESHOLD,
    )


def analyse_camera(event: SensorEvent) -> CameraObservation:
    """Interpret a camera sensor event.

    The raw data_value represents the lateral lane offset.  The lane-keeping
    correction mirrors that offset (steer opposite to the deviation), while
    the cruise-control adjustment is set to zero because the camera feed
    carries no speed-error information in this simulation.
    """
    return CameraObservation(
        lane_keeping_correction=event.data_value,
        cruise_control_adjustment=0.0,
    )
