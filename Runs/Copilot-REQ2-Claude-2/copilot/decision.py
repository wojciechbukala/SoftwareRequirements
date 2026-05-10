"""Decision logic layer: evaluates autonomous feature outcomes from observations."""

from .models import FeatureDecision
from .perception import LidarObservation, CameraObservation

# Feature name constants
FEATURE_EMERGENCY_BRAKING = "emergency_braking"
FEATURE_LANE_KEEPING = "lane_keeping"
FEATURE_CRUISE_CONTROL = "cruise_control"

# Decision value constants
DECISION_BRAKE = "BRAKE"
DECISION_NO_BRAKE = "NO_BRAKE"


def evaluate_emergency_braking(timestamp: float, obs: LidarObservation) -> FeatureDecision:
    """Produce an emergency-braking feature decision from a Lidar observation."""
    decision = DECISION_BRAKE if obs.emergency_brake_required else DECISION_NO_BRAKE
    return FeatureDecision(timestamp=timestamp, feature=FEATURE_EMERGENCY_BRAKING, decision=decision)


def evaluate_lane_keeping(timestamp: float, obs: CameraObservation) -> FeatureDecision:
    """Produce a lane-keeping feature decision from a camera observation."""
    return FeatureDecision(
        timestamp=timestamp,
        feature=FEATURE_LANE_KEEPING,
        decision=obs.lane_keeping_correction,
    )


def evaluate_cruise_control(timestamp: float, obs: CameraObservation) -> FeatureDecision:
    """Produce a cruise-control feature decision from a camera observation."""
    return FeatureDecision(
        timestamp=timestamp,
        feature=FEATURE_CRUISE_CONTROL,
        decision=obs.cruise_control_adjustment,
    )
