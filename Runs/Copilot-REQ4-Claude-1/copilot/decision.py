"""Decision logic layer: map sensor readings to ADAS feature decisions."""

from .models import FeatureDecisionEntry, SensorEvent, State

# Obstacle distance below which emergency braking is required (metres)
LIDAR_DANGER_THRESHOLD: float = 5.0


def evaluate_emergency_braking(event: SensorEvent) -> FeatureDecisionEntry:
    """Return an EmergencyBraking decision for the given Lidar reading.

    Decision is BRAKE when the measured distance is below the danger threshold,
    NO_BRAKE otherwise.
    """
    decision = "BRAKE" if event.data_value < LIDAR_DANGER_THRESHOLD else "NO_BRAKE"
    return FeatureDecisionEntry(
        timestamp=event.timestamp,
        feature="EmergencyBraking",
        decision=decision,
    )


def evaluate_lane_keeping(event: SensorEvent) -> FeatureDecisionEntry:
    """Return a LaneKeeping ADJUST decision for the given Camera reading."""
    return FeatureDecisionEntry(
        timestamp=event.timestamp,
        feature="LaneKeeping",
        decision="ADJUST",
    )


def evaluate_cruise_control(event: SensorEvent) -> FeatureDecisionEntry:
    """Return a CruiseControl ADJUST decision for the given Camera reading."""
    return FeatureDecisionEntry(
        timestamp=event.timestamp,
        feature="CruiseControl",
        decision="ADJUST",
    )
