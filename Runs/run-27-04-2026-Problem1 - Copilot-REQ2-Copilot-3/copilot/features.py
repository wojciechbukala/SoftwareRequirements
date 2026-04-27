"""Decision logic: autonomous feature evaluation (FR-02, PF-01)."""

# Threshold below which a Lidar reading triggers emergency braking (metres).
EMERGENCY_BRAKE_DISTANCE_M = 5.0

# Lane keeping gain: steering correction per unit of lateral camera deviation.
LANE_KEEPING_GAIN = -0.5

# Cruise control gain: speed adjustment per unit of camera data value.
CRUISE_CONTROL_GAIN = 0.1


def evaluate_emergency_braking(distance_m: float) -> tuple[bool, str]:
    """Return (should_brake, decision_label) for a Lidar reading.

    Should brake when distance is strictly less than the critical threshold (FR-02).
    """
    if distance_m < EMERGENCY_BRAKE_DISTANCE_M:
        return True, "BRAKE"
    return False, "NO_BRAKE"


def compute_lane_keeping_correction(camera_value: float) -> float:
    """Compute a proportional steering correction from the camera lateral deviation.

    A positive camera_value indicates rightward lane drift; the correction steers left.
    """
    return round(LANE_KEEPING_GAIN * camera_value, 4)


def compute_cruise_control_adjustment(camera_value: float) -> float:
    """Compute a speed adjustment from the camera data value.

    Scales the raw camera reading by a fixed gain to produce a throttle delta.
    """
    return round(CRUISE_CONTROL_GAIN * camera_value, 4)
