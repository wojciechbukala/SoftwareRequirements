"""
Decision layer — feature evaluation logic.

This module translates processed sensor readings into high-level feature
decisions (e.g. whether to brake, what steering correction to apply).

Each public function returns a list of :class:`FeatureDecision` objects so
that the event loop can accumulate and persist them to *feature_decision.csv*.

Feature rules (PF-01)
---------------------
LIDAR  (always evaluated, regardless of system state):
    data_value < 5.0  → decision "BRAKE"   for feature "emergency_braking"
    data_value ≥ 5.0  → decision "NO_BRAKE" for feature "emergency_braking"

Camera (only evaluated while system is in Engaged state):
    lane_keeping   decision = data_value   (correction magnitude)
    cruise_control decision = data_value   (adjustment magnitude)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


# ---------------------------------------------------------------------------
# FeatureDecision dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeatureDecision:
    """
    A single feature evaluation result.

    Attributes:
        timestamp: When the decision was made (mirrors the triggering event).
        feature:   Name of the evaluated feature, e.g. "emergency_braking".
        decision:  Outcome value — either a string label or a numeric quantity.
    """

    timestamp: float
    feature: str
    decision: Union[str, float]


# ---------------------------------------------------------------------------
# LIDAR evaluation
# ---------------------------------------------------------------------------

LIDAR_BRAKE_THRESHOLD: float = 5.0  # metres — below this distance → BRAKE


def evaluate_lidar(timestamp: float, data_value: float) -> list[FeatureDecision]:
    """
    Evaluate emergency braking from a LIDAR reading.

    This function is **always** called regardless of the current system state.

    Args:
        timestamp:  Timestamp of the originating sensor event.
        data_value: Distance to the nearest obstacle in metres.

    Returns:
        A one-element list containing the "emergency_braking" decision.
        The decision value is the string ``"BRAKE"`` when the distance is
        below :data:`LIDAR_BRAKE_THRESHOLD`, otherwise ``"NO_BRAKE"``.
    """
    decision_value: str = "BRAKE" if data_value < LIDAR_BRAKE_THRESHOLD else "NO_BRAKE"
    return [FeatureDecision(timestamp=timestamp, feature="emergency_braking", decision=decision_value)]


# ---------------------------------------------------------------------------
# Camera evaluation
# ---------------------------------------------------------------------------

def evaluate_camera(timestamp: float, data_value: float) -> list[FeatureDecision]:
    """
    Evaluate lane-keeping correction and cruise-control adjustment from a
    Camera reading.

    This function must **only** be called when the system is in the Engaged
    state (enforcement is the caller's responsibility).

    The lane-keeping correction and cruise-control adjustment are both derived
    directly from *data_value* in this simplified simulation model.

    Args:
        timestamp:  Timestamp of the originating sensor event.
        data_value: Raw camera measurement used as the correction signal.

    Returns:
        A two-element list:
        1. ``("lane_keeping", data_value)`` — lateral correction.
        2. ``("cruise_control", data_value)`` — longitudinal adjustment.
    """
    lane_correction: float = data_value
    cruise_adjustment: float = data_value
    return [
        FeatureDecision(timestamp=timestamp, feature="lane_keeping", decision=lane_correction),
        FeatureDecision(timestamp=timestamp, feature="cruise_control", decision=cruise_adjustment),
    ]
