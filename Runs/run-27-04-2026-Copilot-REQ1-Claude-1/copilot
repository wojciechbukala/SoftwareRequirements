#!/usr/bin/env python3
"""Copilot - Driver Assistance System Onboard Computer"""

import argparse
import csv
import os
import sys
from datetime import datetime
from enum import Enum

# ── Constants ────────────────────────────────────────────────────────────────
ATTENTIVENESS_INTERVAL = 120.0   # seconds between attentiveness prompts
ATTENTIVENESS_TIMEOUT  = 5.0     # seconds driver has to respond
EMERGENCY_BRAKE_DIST   = 5.0     # metres – Lidar threshold (strict <)
VALID_FORCE_MAX        = 3.0     # N  – max force for valid attentiveness response
DISENGAGE_FORCE_MIN    = 10.0    # N  – force strictly > this causes disengagement


# ── Helpers ──────────────────────────────────────────────────────────────────
def parse_ts(ts_str: str) -> float:
    """Return a float (seconds) from a numeric or ISO-8601 timestamp string."""
    s = ts_str.strip()
    try:
        return float(s)
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised timestamp format: {ts_str!r}")


def write_csv(path: str, fieldnames: list, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ── State machine ─────────────────────────────────────────────────────────────
class State(Enum):
    DISENGAGED = "DISENGAGED"
    ENGAGED    = "ENGAGED"
    ALARM      = "ALARM"


class Copilot:
    def __init__(self):
        self.state = State.DISENGAGED

        # Output records
        self.state_log:        list[dict] = []
        self.commands_log:     list[dict] = []
        self.feature_decisions: list[dict] = []

        # Attentiveness-check state (float timestamps)
        self.attn_reset_f:  float | None = None   # time of last successful reset
        self.attn_prompt_f: float | None = None   # time prompt was issued
        self.waiting:       bool         = False   # True while waiting for response

    # ── Output helpers ────────────────────────────────────────────────────────
    def _transition(self, ts_str: str, new_state: State, trigger: str) -> None:
        if new_state == self.state:
            return
        self.state_log.append({
            "timestamp":      ts_str,
            "previous_state": self.state.value,
            "current_state":  new_state.value,
            "trigger_event":  trigger,
        })
        self.state = new_state

    def _command(self, ts_str: str, actuator_id: str, values: str) -> None:
        self.commands_log.append({
            "timestamp":   ts_str,
            "actuator_id": actuator_id,
            "values":      values,
        })

    def _decision(self, ts_str: str, feature: str, decision: str) -> None:
        self.feature_decisions.append({
            "timestamp": ts_str,
            "feature":   feature,
            "decision":  decision,
        })

    # ── Attentiveness timer ───────────────────────────────────────────────────
    def _check_attentiveness(self, ts_str: str, ts_f: float) -> None:
        """Evaluate attentiveness check; called at the start of every event."""
        if self.state not in (State.ENGAGED, State.ALARM):
            return

        # Issue prompt after 120 s of inactivity (only when engaged, not waiting)
        if self.state == State.ENGAGED and not self.waiting:
            if self.attn_reset_f is not None:
                if ts_f - self.attn_reset_f >= ATTENTIVENESS_INTERVAL:
                    self._command(ts_str, "SteeringWheel", "small_movement")
                    self.attn_prompt_f = ts_f
                    self.waiting = True

        # Detect timeout: >5 s with no valid response
        if self.waiting and self.attn_prompt_f is not None:
            if ts_f - self.attn_prompt_f > ATTENTIVENESS_TIMEOUT:
                if self.state != State.ALARM:
                    self._command(ts_str, "Alarm", "on")
                    self._transition(ts_str, State.ALARM, "attentiveness_timeout")

    # ── Feature evaluations ───────────────────────────────────────────────────
    def _eval_emergency_braking(self, ts_str: str, distance: float) -> None:
        if distance < EMERGENCY_BRAKE_DIST:
            self._decision(ts_str, "emergency braking", "BRAKE")
            self._command(ts_str, "BrakingSystem", "emergency_brake")
        else:
            self._decision(ts_str, "emergency braking", "NO_BRAKE")

    def _eval_lane_keeping(self, ts_str: str, lane_offset: float) -> None:
        correction = round(-lane_offset * 0.5, 4)
        self._decision(ts_str, "lane keeping", str(correction))
        self._command(ts_str, "SteeringActuator", str(correction))

    def _eval_cruise_control(self, ts_str: str, data_value: float) -> None:
        correction = round(data_value, 4)
        self._decision(ts_str, "cruise control", str(correction))
        self._command(ts_str, "ThrottleActuator", str(correction))

    # ── Steering-force handler (shared logic) ─────────────────────────────────
    def _handle_steering_force(self, ts_str: str, ts_f: float, force: float) -> None:
        # Force > 10 N → immediate disengagement (highest priority)
        if force > DISENGAGE_FORCE_MIN:
            if self.state != State.DISENGAGED:
                self._transition(ts_str, State.DISENGAGED, "steering_wheel_force")
            self.waiting = False
            self.attn_prompt_f = None
            return

        # If currently waiting for an attentiveness response …
        if self.waiting:
            if force <= VALID_FORCE_MAX:
                # Valid response: clear alarm if active, restart timer
                if self.state == State.ALARM:
                    self._command(ts_str, "Alarm", "off")
                    self._transition(ts_str, State.ENGAGED, "attentiveness_response")
                self.waiting = False
                self.attn_prompt_f = None
                self.attn_reset_f = ts_f
            # 3 < force ≤ 10: ignore (spec §3), keep waiting

    # ── Event dispatchers ─────────────────────────────────────────────────────
    def process_sensor(
        self,
        ts_str: str,
        ts_f: float,
        sensor_id: str,
        sensor_type: str,
        data_value: float,
        unit: str,
    ) -> None:
        self._check_attentiveness(ts_str, ts_f)

        st = sensor_type.strip().lower()

        # Emergency braking is always active on every Lidar reading
        if "lidar" in st:
            self._eval_emergency_braking(ts_str, data_value)

        # Lane keeping and cruise control are engaged-only, camera-triggered
        if self.state == State.ENGAGED and "camera" in st:
            self._eval_lane_keeping(ts_str, data_value)
            self._eval_cruise_control(ts_str, data_value)

    def process_driver_event(
        self, ts_str: str, ts_f: float, event_type: str, value: str
    ) -> None:
        self._check_attentiveness(ts_str, ts_f)

        et      = event_type.strip().lower()
        val_str = str(value).strip().lower()

        try:
            val_f: float | None = float(value)
        except (ValueError, TypeError):
            val_f = None

        # Steering wheel force
        if "steering_wheel_force" in et or et == "steering_force":
            if val_f is not None:
                self._handle_steering_force(ts_str, ts_f, val_f)
            return

        # Engage
        if et == "engage" or (et == "mode_change" and val_str in ("engaged", "engage", "1")):
            if self.state == State.DISENGAGED:
                self._transition(ts_str, State.ENGAGED, "engage")
                self.attn_reset_f  = ts_f
                self.waiting       = False
                self.attn_prompt_f = None
            return

        # Disengage
        if et == "disengage" or (et == "mode_change" and val_str in ("disengaged", "disengage", "0")):
            if self.state != State.DISENGAGED:
                self._transition(ts_str, State.DISENGAGED, "disengage")
                self.waiting       = False
                self.attn_prompt_f = None
            return


# ── I/O ──────────────────────────────────────────────────────────────────────
def load_sensor_log(path: str) -> list[dict]:
    events = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ts_str = row["timestamp"].strip()
            events.append({
                "ts_str":      ts_str,
                "ts_f":        parse_ts(ts_str),
                "source":      "sensor",
                "sensor_id":   row.get("sensor_id",   "").strip(),
                "sensor_type": row.get("sensor_type", "").strip(),
                "data_value":  float(row.get("data_value", 0)),
                "unit":        row.get("unit", "").strip(),
            })
    return events


def load_driver_events(path: str) -> list[dict]:
    events = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ts_str = row["timestamp"].strip()
            events.append({
                "ts_str":     ts_str,
                "ts_f":       parse_ts(ts_str),
                "source":     "driver",
                "event_type": row.get("event_type", "").strip(),
                "value":      row.get("value",      "").strip(),
            })
    return events


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copilot – Driver Assistance Onboard Computer"
    )
    parser.add_argument("--input",  required=True, help="Input directory")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

    in_dir  = args.input
    out_dir = args.output
    os.makedirs(out_dir, exist_ok=True)

    sensor_path = os.path.join(in_dir, "sensor_log.csv")
    driver_path = os.path.join(in_dir, "driver_events.csv")

    sensor_events = load_sensor_log(sensor_path) if os.path.isfile(sensor_path) else []
    driver_events = load_driver_events(driver_path) if os.path.isfile(driver_path) else []

    # Merge and sort (stable) by ascending timestamp
    all_events = sorted(sensor_events + driver_events, key=lambda e: e["ts_f"])

    copilot = Copilot()

    for ev in all_events:
        ts_str, ts_f = ev["ts_str"], ev["ts_f"]
        if ev["source"] == "sensor":
            copilot.process_sensor(
                ts_str, ts_f,
                ev["sensor_id"], ev["sensor_type"], ev["data_value"], ev["unit"],
            )
        else:
            copilot.process_driver_event(
                ts_str, ts_f, ev["event_type"], ev["value"]
            )

    write_csv(
        os.path.join(out_dir, "state_log.csv"),
        ["timestamp", "previous_state", "current_state", "trigger_event"],
        copilot.state_log,
    )
    write_csv(
        os.path.join(out_dir, "commands_log.csv"),
        ["timestamp", "actuator_id", "values"],
        copilot.commands_log,
    )
    write_csv(
        os.path.join(out_dir, "feature_decision.csv"),
        ["timestamp", "feature", "decision"],
        copilot.feature_decisions,
    )


if __name__ == "__main__":
    main()
