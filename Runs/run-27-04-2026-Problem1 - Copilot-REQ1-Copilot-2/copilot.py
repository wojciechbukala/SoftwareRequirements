#!/usr/bin/env python3
"""Copilot - Driver Assistance System Onboard Computer Simulator"""

import argparse
import csv
import os

ATTENTIVENESS_INTERVAL = 120.0  # seconds between attentiveness checks
ATTENTIVENESS_WINDOW = 5.0      # seconds driver has to respond to prompt
FORCE_VALID_MAX = 3.0           # N - max force for a valid attentiveness response
FORCE_OVERRIDE = 10.0           # N - force strictly above this causes immediate disengagement
BRAKE_DISTANCE = 5.0            # m - Lidar distance strictly below this triggers emergency brake

STATE_DISENGAGED = "disengaged"
STATE_ENGAGED = "engaged"
STATE_ALARM = "alarm"


def parse_timestamp(ts_str):
    try:
        return float(ts_str)
    except (ValueError, TypeError):
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(str(ts_str).strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()


class CopilotSystem:
    def __init__(self):
        self.state = STATE_DISENGAGED
        self.state_log = []
        self.commands_log = []
        self.feature_decisions = []

        self.attn_timer_start = None   # timestamp when 120-sec timer was (re)started
        self.attn_prompt_time = None   # timestamp when current prompt was issued
        self.in_attn_window = False    # True while waiting within the 5-sec response window

    # ------------------------------------------------------------------ helpers

    def _transition(self, ts, new_state, trigger):
        if new_state != self.state:
            self.state_log.append({
                'timestamp': ts,
                'previous_state': self.state,
                'current_state': new_state,
                'trigger_event': trigger,
            })
            self.state = new_state

    def _command(self, ts, actuator, values):
        self.commands_log.append({
            'timestamp': ts,
            'actuator_id': actuator,
            'values': values,
        })

    def _decision(self, ts, feature, decision):
        self.feature_decisions.append({
            'timestamp': ts,
            'feature': feature,
            'decision': decision,
        })

    # -------------------------------------------------------- timer management

    def _check_timers(self, current_ts):
        """Inject any time-based events (attentiveness prompt / alarm) due before current_ts."""
        if self.state not in (STATE_ENGAGED, STATE_ALARM):
            return

        if self.in_attn_window:
            # Check whether the 5-second response window has expired.
            window_end = self.attn_prompt_time + ATTENTIVENESS_WINDOW
            if current_ts > window_end and self.state == STATE_ENGAGED:
                self._command(window_end, 'Alarm System', 'alarm_on')
                self._transition(window_end, STATE_ALARM, 'attentiveness_timeout')
                self.in_attn_window = False
            return

        # Not in a response window — check whether a new prompt is due.
        while self.state == STATE_ENGAGED and self.attn_timer_start is not None:
            prompt_due = self.attn_timer_start + ATTENTIVENESS_INTERVAL
            if current_ts < prompt_due:
                break

            # Issue the attentiveness prompt at the exact due time.
            self._command(prompt_due, 'Steering System', 'attentiveness_prompt')
            self.attn_prompt_time = prompt_due
            self.in_attn_window = True

            window_end = prompt_due + ATTENTIVENESS_WINDOW
            if current_ts > window_end:
                # Response window already expired — trigger alarm.
                self._command(window_end, 'Alarm System', 'alarm_on')
                self._transition(window_end, STATE_ALARM, 'attentiveness_timeout')
                self.in_attn_window = False
                break  # Now in ALARM; no further prompts until driver responds.
            else:
                break  # Still inside the window; wait for a driver event.

    # -------------------------------------------------------- event processors

    def _handle_steering_force(self, ts, force):
        # Strictly greater than 10 N always causes immediate disengagement.
        if force > FORCE_OVERRIDE:
            if self.state in (STATE_ENGAGED, STATE_ALARM):
                if self.state == STATE_ALARM:
                    self._command(ts, 'Alarm System', 'alarm_off')
                self._transition(ts, STATE_DISENGAGED, 'steering_force_override')
                self.attn_timer_start = None
                self.attn_prompt_time = None
                self.in_attn_window = False
            return

        # Only act on steering forces during the attentiveness window or in alarm.
        if not (self.in_attn_window or self.state == STATE_ALARM):
            return

        if force <= FORCE_VALID_MAX:
            # Valid response: clear alarm / window and restart the 120-sec timer.
            if self.state == STATE_ALARM:
                self._command(ts, 'Alarm System', 'alarm_off')
                self._transition(ts, STATE_ENGAGED, 'driver_response')
            self.in_attn_window = False
            self.attn_prompt_time = None
            self.attn_timer_start = ts  # restart 120-sec timer from this moment
        # 3 N < force <= 10 N: ignored — system keeps waiting.

    def process_sensor(self, ts, event):
        self._check_timers(ts)

        sensor_type = event.get('sensor_type', '').lower()
        try:
            value = float(event.get('data_value', 0))
        except (ValueError, TypeError):
            value = 0.0

        # Emergency braking — always active regardless of mode.
        if 'lidar' in sensor_type:
            if value < BRAKE_DISTANCE:
                self._command(ts, 'Braking System', 'emergency_brake')
                self._decision(ts, 'emergency braking', 'BRAKE')
            else:
                self._decision(ts, 'emergency braking', 'NO_BRAKE')
            return  # Lidar reading handled; nothing else to do.

        # Lane keeping and cruise control — active only when engaged (or alarm).
        if self.state not in (STATE_ENGAGED, STATE_ALARM):
            return

        if 'camera' in sensor_type:
            self._command(ts, 'Steering System', str(value))
            self._decision(ts, 'lane keeping', str(value))
        else:
            # Any other sensor type (speed, radar, …) feeds cruise control.
            self._command(ts, 'Engine Control', str(value))
            self._decision(ts, 'cruise control', str(value))

    def process_driver_event(self, ts, event):
        self._check_timers(ts)

        event_type = event.get('event_type', '')
        try:
            value = float(event.get('value', 0))
        except (ValueError, TypeError):
            value = 0.0

        if event_type == 'engage':
            if self.state == STATE_DISENGAGED:
                self._transition(ts, STATE_ENGAGED, 'driver_engage')
                self.attn_timer_start = ts
                self.in_attn_window = False
                self.attn_prompt_time = None

        elif event_type == 'disengage':
            if self.state in (STATE_ENGAGED, STATE_ALARM):
                if self.state == STATE_ALARM:
                    self._command(ts, 'Alarm System', 'alarm_off')
                self._transition(ts, STATE_DISENGAGED, 'driver_disengage')
                self.attn_timer_start = None
                self.attn_prompt_time = None
                self.in_attn_window = False

        elif event_type == 'steering_wheel_force':
            self._handle_steering_force(ts, value)

    # ---------------------------------------------------------------- main run

    def run(self, sensor_events, driver_events):
        all_events = []
        for e in sensor_events:
            try:
                ts = parse_timestamp(e['timestamp'])
                all_events.append((ts, 0, 'sensor', e))
            except (ValueError, KeyError):
                continue
        for e in driver_events:
            try:
                ts = parse_timestamp(e['timestamp'])
                all_events.append((ts, 1, 'driver', e))
            except (ValueError, KeyError):
                continue

        # Primary sort by timestamp; sensor events before driver events on ties.
        all_events.sort(key=lambda x: (x[0], x[1]))

        for ts, _, kind, event in all_events:
            if kind == 'sensor':
                self.process_sensor(ts, event)
            else:
                self.process_driver_event(ts, event)


# ------------------------------------------------------------------ I/O helpers

def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_csv(path, fieldnames, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt_ts(ts):
    """Format a timestamp for output — preserve integer appearance when possible."""
    if ts == int(ts):
        return str(int(ts))
    return str(ts)


def format_output_rows(rows, ts_field='timestamp'):
    """Convert float timestamps to clean string representation."""
    result = []
    for row in rows:
        r = dict(row)
        r[ts_field] = fmt_ts(r[ts_field])
        result.append(r)
    return result


# --------------------------------------------------------------------- entry

def main():
    parser = argparse.ArgumentParser(description='Copilot Driver Assistance System')
    parser.add_argument('--input', required=True, help='Directory containing input CSV files')
    parser.add_argument('--output', required=True, help='Directory for output CSV files')
    args = parser.parse_args()

    sensor_events = read_csv(os.path.join(args.input, 'sensor_log.csv'))
    driver_events = read_csv(os.path.join(args.input, 'driver_events.csv'))

    copilot = CopilotSystem()
    copilot.run(sensor_events, driver_events)

    os.makedirs(args.output, exist_ok=True)

    write_csv(
        os.path.join(args.output, 'state_log.csv'),
        ['timestamp', 'previous_state', 'current_state', 'trigger_event'],
        format_output_rows(copilot.state_log),
    )
    write_csv(
        os.path.join(args.output, 'commands_log.csv'),
        ['timestamp', 'actuator_id', 'values'],
        format_output_rows(copilot.commands_log),
    )
    write_csv(
        os.path.join(args.output, 'feature_decision.csv'),
        ['timestamp', 'feature', 'decision'],
        format_output_rows(copilot.feature_decisions),
    )


if __name__ == '__main__':
    main()
