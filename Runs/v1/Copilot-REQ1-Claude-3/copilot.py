#!/usr/bin/env python3
"""Copilot — onboard computer for a driver-assistance system."""
import argparse
import csv
import os
from typing import Optional

ATTENTIVENESS_INTERVAL = 120.0   # seconds between attentiveness prompts
ATTENTIVENESS_TIMEOUT  = 5.0     # seconds to wait for driver response
BRAKE_THRESHOLD        = 5.0     # metres — Lidar distance that triggers e-brake
DISENGAGE_FORCE        = 10.0    # N  — force that forces disengagement (strictly >)
VALID_FORCE_MAX        = 3.0     # N  — max force for a valid attentiveness response


def _parse_ts(raw: str) -> float:
    """Parse a timestamp that is either a plain float or an ISO-8601 string."""
    raw = raw.strip()
    try:
        return float(raw)
    except ValueError:
        from datetime import datetime, timezone
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(raw, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.timestamp()
            except ValueError:
                continue
        raise ValueError(f"Unrecognised timestamp format: {raw!r}")


class CopilotSystem:
    DISENGAGED = "DISENGAGED"
    ENGAGED    = "ENGAGED"

    def __init__(self, output_dir: str) -> None:
        self.state: str = self.DISENGAGED

        os.makedirs(output_dir, exist_ok=True)

        self._sf = open(os.path.join(output_dir, "state_log.csv"),       "w", newline="", encoding="utf-8")
        self._cf = open(os.path.join(output_dir, "commands_log.csv"),     "w", newline="", encoding="utf-8")
        self._ff = open(os.path.join(output_dir, "feature_decision.csv"), "w", newline="", encoding="utf-8")

        self._sw = csv.writer(self._sf)
        self._cw = csv.writer(self._cf)
        self._fw = csv.writer(self._ff)

        self._sw.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
        self._cw.writerow(["timestamp", "actuator_id", "values"])
        self._fw.writerow(["timestamp", "feature", "decision"])

        # Attentiveness tracking
        self.next_check_time: Optional[float] = None   # wall-clock timestamp for next prompt
        self.waiting_since:   Optional[float] = None   # timestamp of last prompt, while awaiting reply
        self.alarm_active:    bool            = False

    # ------------------------------------------------------------------ #
    # Low-level output helpers                                             #
    # ------------------------------------------------------------------ #

    def _transition(self, ts_str: str, new_state: str, trigger: str) -> None:
        if new_state != self.state:
            self._sw.writerow([ts_str, self.state, new_state, trigger])
            self.state = new_state

    def _command(self, ts_str: str, actuator_id: str, values) -> None:
        self._cw.writerow([ts_str, actuator_id, values])

    def _decision(self, ts_str: str, feature: str, decision) -> None:
        self._fw.writerow([ts_str, feature, decision])

    # ------------------------------------------------------------------ #
    # Attentiveness logic                                                  #
    # ------------------------------------------------------------------ #

    def _check_attentiveness_timing(self, ts: float, ts_str: str) -> None:
        """Evaluate time-based attentiveness conditions at event timestamp ts."""
        if self.state != self.ENGAGED:
            return

        if self.waiting_since is not None:
            # Already waiting for a response
            elapsed = ts - self.waiting_since
            if elapsed > ATTENTIVENESS_TIMEOUT and not self.alarm_active:
                self._command(ts_str, "Alarm", "ON")
                self.alarm_active = True
            return

        # Not waiting — check if a new prompt is due
        if self.next_check_time is not None and ts >= self.next_check_time:
            self._command(ts_str, "SteeringWheel", "HAPTIC")
            self.waiting_since = ts

    def _handle_attentiveness_response(self, ts: float, ts_str: str, force: float) -> None:
        """Process a steering-wheel force as a potential attentiveness response."""
        if self.waiting_since is None:
            return

        elapsed = ts - self.waiting_since

        if elapsed <= ATTENTIVENESS_TIMEOUT:
            # Within the 5-second window
            if force <= VALID_FORCE_MAX:
                self._accept_response(ts, ts_str)
            # 3 < force <= 10: ignored per spec, keep waiting
        else:
            # Past the 5-second window (alarm may or may not be active yet)
            if force <= VALID_FORCE_MAX:
                self._accept_response(ts, ts_str)
            # Otherwise continue waiting with alarm on

    def _accept_response(self, ts: float, ts_str: str) -> None:
        """Driver gave a valid attentiveness response; reset the interval."""
        if self.alarm_active:
            self._command(ts_str, "Alarm", "OFF")
            self.alarm_active = False
        self.waiting_since    = None
        self.next_check_time  = ts + ATTENTIVENESS_INTERVAL

    # ------------------------------------------------------------------ #
    # Engage / Disengage                                                   #
    # ------------------------------------------------------------------ #

    def _engage(self, ts: float, ts_str: str, trigger: str) -> None:
        if self.state == self.DISENGAGED:
            self._transition(ts_str, self.ENGAGED, trigger)
            self.next_check_time = ts + ATTENTIVENESS_INTERVAL
            self.waiting_since   = None
            self.alarm_active    = False

    def _disengage(self, ts_str: str, trigger: str) -> None:
        if self.alarm_active:
            self._command(ts_str, "Alarm", "OFF")
            self.alarm_active = False
        self.next_check_time = None
        self.waiting_since   = None
        self._transition(ts_str, self.DISENGAGED, trigger)

    # ------------------------------------------------------------------ #
    # Feature computations                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _lane_correction(offset: float) -> str:
        return str(round(-offset * 0.5, 4))

    @staticmethod
    def _speed_adjustment(distance: float) -> str:
        # Proportional deceleration if following distance < 30 m
        if distance >= 30.0:
            return "0.0"
        return str(round((distance - 30.0) * 0.5, 4))

    # ------------------------------------------------------------------ #
    # Public event processors                                              #
    # ------------------------------------------------------------------ #

    def process_sensor(
        self,
        ts: float,
        ts_str: str,
        sensor_id: str,
        sensor_type: str,
        data_value: float,
        unit: str,
    ) -> None:
        self._check_attentiveness_timing(ts, ts_str)

        st = sensor_type.lower().strip()

        if st == "lidar":
            # Emergency braking — always active regardless of mode
            if data_value < BRAKE_THRESHOLD:
                self._decision(ts_str, "emergency braking", "BRAKE")
                self._command(ts_str, "BrakingSystem", "ENGAGE")
            else:
                self._decision(ts_str, "emergency braking", "NO_BRAKE")
                # Cruise control — only while engaged, and only when not braking
                if self.state == self.ENGAGED:
                    adj = self._speed_adjustment(data_value)
                    self._decision(ts_str, "cruise control", adj)
                    self._command(ts_str, "ThrottleActuator", adj)

        elif st == "camera":
            # Lane keeping — only while engaged
            if self.state == self.ENGAGED:
                corr = self._lane_correction(data_value)
                self._decision(ts_str, "lane keeping", corr)
                self._command(ts_str, "SteeringActuator", corr)

    def process_driver(
        self,
        ts: float,
        ts_str: str,
        event_type: str,
        value: str,
    ) -> None:
        et = event_type.lower().strip()

        if et in ("steering_wheel_force", "steering_force", "swf"):
            try:
                force = float(value)
            except (ValueError, TypeError):
                force = 0.0

            # Evaluate timing before handling the force event
            self._check_attentiveness_timing(ts, ts_str)

            # Force > 10 N → immediate disengagement
            if force > DISENGAGE_FORCE:
                if self.state == self.ENGAGED:
                    self._disengage(ts_str, event_type)
                return

            if self.state == self.ENGAGED:
                self._handle_attentiveness_response(ts, ts_str, force)
            return

        # Non-force driver events
        self._check_attentiveness_timing(ts, ts_str)

        if et == "engage":
            self._engage(ts, ts_str, event_type)
        elif et == "disengage":
            if self.state == self.ENGAGED:
                self._disengage(ts_str, event_type)

    def close(self) -> None:
        self._sf.close()
        self._cf.close()
        self._ff.close()


# ------------------------------------------------------------------ #
# Entry point                                                         #
# ------------------------------------------------------------------ #

def _load_sensor_events(path: str) -> list:
    events = []
    if not os.path.exists(path):
        return events
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ts_str = row["timestamp"].strip()
            events.append((
                _parse_ts(ts_str),
                ts_str,
                "sensor",
                row["sensor_id"].strip(),
                row["sensor_type"].strip(),
                float(row["data_value"].strip()),
                row.get("unit", "").strip(),
            ))
    return events


def _load_driver_events(path: str) -> list:
    events = []
    if not os.path.exists(path):
        return events
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ts_str = row["timestamp"].strip()
            events.append((
                _parse_ts(ts_str),
                ts_str,
                "driver",
                row["event_type"].strip(),
                row.get("value", "").strip(),
            ))
    return events


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="copilot",
        description="Copilot driver-assistance onboard computer",
    )
    parser.add_argument("--input",  required=True, metavar="DIR", help="Directory containing input CSV files")
    parser.add_argument("--output", required=True, metavar="DIR", help="Directory for output CSV files")
    args = parser.parse_args()

    sensor_events = _load_sensor_events(os.path.join(args.input, "sensor_log.csv"))
    driver_events = _load_driver_events(os.path.join(args.input, "driver_events.csv"))

    # Merge and sort by timestamp; Python sort is stable so same-ts ties keep
    # file order (sensor events placed before driver events within a tie).
    all_events = sensor_events + driver_events
    all_events.sort(key=lambda e: e[0])

    system = CopilotSystem(args.output)
    try:
        for event in all_events:
            if event[2] == "sensor":
                _, ts_str, _, sensor_id, sensor_type, data_value, unit = event
                system.process_sensor(event[0], ts_str, sensor_id, sensor_type, data_value, unit)
            else:
                _, ts_str, _, event_type, value = event
                system.process_driver(event[0], ts_str, event_type, value)
    finally:
        system.close()


if __name__ == "__main__":
    main()
