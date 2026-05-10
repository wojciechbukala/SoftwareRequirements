"""
Copilot — driver-assistance simulation package.

This package implements a driver-assistance system that reads sensor and
driver-event CSV files, runs them through a state machine with perception
and decision layers, and writes structured output CSV files.
"""

__version__ = "1.0.0"
__all__ = ["perception", "state_machine", "decision", "actuator", "output"]
