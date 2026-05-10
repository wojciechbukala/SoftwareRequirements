#!/usr/bin/env python3
"""Copilot driver-assistance system simulator."""
import argparse
import csv
import heapq
import os

DISENGAGED = "disengaged"
ENGAGED = "engaged"
ALARM = "alarm"

ATTENTIVENESS_INTERVAL = 120.0  # seconds between attentiveness prompts
RESPONSE_WINDOW = 5.0           # seconds to wait for driver response
FORCE_VALID_MAX = 3.0           # N  - max force for valid attentiveness response
FORCE_DISENGAGE = 10.0          # N  - strictly above this causes disengagement
EMERGENCY_BRAKE_DIST = 5.0      # m  - strictly below this triggers emergency braking


def simulate(input_dir, output_dir):
    # ── Load inputs ──────────────────────────────────────────────────────────
    sensor_events, driver_events = [], []

    with open(os.path.join(input_dir, "sensor_log.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sensor_events.append(("sensor", float(row["timestamp"]), row))

    with open(os.path.join(input_dir, "driver_events.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            driver_events.append(("driver", float(row["timestamp"]), row))

    all_events = sorted(sensor_events + driver_events, key=lambda e: e[1])

    # ── Output collections ───────────────────────────────────────────────────
    state_log = []
    commands_log = []
    feature_decisions = []

    # ── State ────────────────────────────────────────────────────────────────
    state = DISENGAGED
    in_wait_window = False  # True during 5 s attentiveness response window

    # ── Time-event queue with lazy deletion ──────────────────────────────────
    # Items: (event_time, seq_id, event_type_str)
    time_queue = []
    _seq = [0]
    cancelled = set()
    prompt_eid = [None]
    timeout_eid = [None]

    def push(t, etype):
        _seq[0] += 1
        s = _seq[0]
        heapq.heappush(time_queue, (t, s, etype))
        return s

    def cancel(eid):
        if eid is not None:
            cancelled.add(eid)

    # ── Helper emitters ──────────────────────────────────────────────────────
    def log_transition(ts, prev, cur, trigger):
        state_log.append({
            "timestamp": ts,
            "previous_state": prev,
            "current_state": cur,
            "trigger_event": trigger,
        })

    def cmd(ts, actuator, values):
        commands_log.append({"timestamp": ts, "actuator_id": actuator, "values": values})

    def dec(ts, feature, decision):
        feature_decisions.append({"timestamp": ts, "feature": feature, "decision": decision})

    # ── State-change helpers ─────────────────────────────────────────────────
    def transition(ts, new_state, trigger):
        nonlocal state
        if new_state != state:
            log_transition(ts, state, new_state, trigger)
            state = new_state

    def schedule_prompt(from_time):
        cancel(prompt_eid[0])
        prompt_eid[0] = push(from_time + ATTENTIVENESS_INTERVAL, "prompt")

    def do_engage(ts, trigger):
        nonlocal in_wait_window
        transition(ts, ENGAGED, trigger)
        in_wait_window = False
        schedule_prompt(ts)

    def do_disengage(ts, trigger):
        nonlocal in_wait_window
        transition(ts, DISENGAGED, trigger)
        in_wait_window = False
        cancel(prompt_eid[0]);  prompt_eid[0] = None
        cancel(timeout_eid[0]); timeout_eid[0] = None

    def handle_valid_response(ts):
        nonlocal in_wait_window
        in_wait_window = False
        cancel(timeout_eid[0]); timeout_eid[0] = None
        if state == ALARM:
            transition(ts, ENGAGED, "steering_wheel_force")
            cmd(ts, "Alarm", "off")
        schedule_prompt(ts)

    # ── Time-event processor ─────────────────────────────────────────────────
    def process_time_events(up_to):
        nonlocal in_wait_window
        while time_queue and time_queue[0][0] <= up_to:
            evt_time, seq, etype = heapq.heappop(time_queue)
            if seq in cancelled:
                cancelled.discard(seq)
                continue

            if etype == "prompt":
                prompt_eid[0] = None
                if state == ENGAGED:
                    cmd(evt_time, "SteeringWheel", "small_movement")
                    in_wait_window = True
                    cancel(timeout_eid[0])
                    timeout_eid[0] = push(evt_time + RESPONSE_WINDOW, "timeout")

            elif etype == "timeout":
                timeout_eid[0] = None
                if in_wait_window and state == ENGAGED:
                    in_wait_window = False
                    transition(evt_time, ALARM, "attentiveness_timeout")
                    cmd(evt_time, "Alarm", "on")

    # ── Main event loop ──────────────────────────────────────────────────────
    for etype, ts, row in all_events:
        process_time_events(ts)

        if etype == "sensor":
            stype = row["sensor_type"].lower()
            val = float(row["data_value"])

            if stype == "lidar":
                if val < EMERGENCY_BRAKE_DIST:
                    # Emergency braking — always active regardless of mode
                    cmd(ts, "Braking System", "brake")
                    dec(ts, "emergency braking", "BRAKE")
                else:
                    dec(ts, "emergency braking", "NO BRAKE")
                    if state in (ENGAGED, ALARM):
                        # Cruise control: speed factor based on following distance
                        speed_factor = round(min(1.0, (val - EMERGENCY_BRAKE_DIST) / 20.0), 3)
                        cmd(ts, "ThrottleActuator", speed_factor)
                        dec(ts, "cruise control", speed_factor)

            elif stype == "camera":
                if state in (ENGAGED, ALARM):
                    # Lane keeping: correction opposes detected lateral deviation
                    correction = round(-val, 3)
                    cmd(ts, "SteeringActuator", correction)
                    dec(ts, "lane keeping", correction)

        else:  # driver event
            event_type = row["event_type"]
            val = float(row["value"])

            if event_type == "engage":
                if state == DISENGAGED:
                    do_engage(ts, "engage")

            elif event_type == "disengage":
                if state != DISENGAGED:
                    do_disengage(ts, "disengage")

            elif event_type == "steering_wheel_force":
                if val > FORCE_DISENGAGE:
                    if state != DISENGAGED:
                        do_disengage(ts, "steering_wheel_force")
                elif state in (ENGAGED, ALARM):
                    if in_wait_window or state == ALARM:
                        if val <= FORCE_VALID_MAX:
                            handle_valid_response(ts)
                        # 3 N < val <= 10 N: ignored, keep waiting

    # ── Write outputs ─────────────────────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)

    def write_csv(fname, fields, rows):
        with open(os.path.join(output_dir, fname), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    write_csv(
        "state_log.csv",
        ["timestamp", "previous_state", "current_state", "trigger_event"],
        state_log,
    )
    write_csv(
        "commands_log.csv",
        ["timestamp", "actuator_id", "values"],
        commands_log,
    )
    write_csv(
        "feature_decision.csv",
        ["timestamp", "feature", "decision"],
        feature_decisions,
    )


def main():
    parser = argparse.ArgumentParser(description="Copilot driver-assistance system simulator")
    parser.add_argument("--input", required=True, metavar="DIR", help="Input directory")
    parser.add_argument("--output", required=True, metavar="DIR", help="Output directory")
    args = parser.parse_args()
    simulate(args.input, args.output)


if __name__ == "__main__":
    main()
