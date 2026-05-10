#!/usr/bin/env python3
import csv
import argparse
import os

ATTENTIVENESS_INTERVAL = 120.0
ATTENTIVENESS_TIMEOUT = 5.0
EMERGENCY_BRAKE_THRESHOLD = 5.0
FORCE_DISENGAGE_THRESHOLD = 10.0
FORCE_VALID_THRESHOLD = 3.0
ATTENTIVENESS_PROMPT_VALUE = 0.5


class Copilot:
    def __init__(self):
        self.state = 'disengaged'
        self.state_log = []
        self.commands_log = []
        self.feature_decisions = []

        self.last_attentiveness_reset = None
        self.pending_prompt = False
        self.prompt_time = None

    def _transition(self, timestamp, new_state, trigger_event):
        if self.state != new_state:
            self.state_log.append({
                'timestamp': timestamp,
                'previous_state': self.state,
                'current_state': new_state,
                'trigger_event': trigger_event,
            })
            self.state = new_state

    def _add_command(self, timestamp, actuator_id, values):
        self.commands_log.append({
            'timestamp': timestamp,
            'actuator_id': actuator_id,
            'values': values,
        })

    def _add_decision(self, timestamp, feature, decision):
        self.feature_decisions.append({
            'timestamp': timestamp,
            'feature': feature,
            'decision': decision,
        })

    def _check_time_events(self, current_time):
        """Fire time-based events whose due time has passed."""
        if self.state == 'engaged' and not self.pending_prompt:
            if self.last_attentiveness_reset is not None:
                prompt_due = self.last_attentiveness_reset + ATTENTIVENESS_INTERVAL
                if current_time >= prompt_due:
                    self._issue_prompt(prompt_due)

        if self.pending_prompt and self.state == 'engaged':
            alarm_due = self.prompt_time + ATTENTIVENESS_TIMEOUT
            if current_time > alarm_due:
                self._trigger_alarm(alarm_due)

    def _issue_prompt(self, timestamp):
        self.pending_prompt = True
        self.prompt_time = timestamp
        self._add_command(timestamp, 'SteeringWheel', ATTENTIVENESS_PROMPT_VALUE)

    def _trigger_alarm(self, timestamp):
        self._transition(timestamp, 'alarm', 'attentiveness_timeout')
        self._add_command(timestamp, 'Alarm', 'on')

    def _handle_valid_attentiveness_response(self, timestamp):
        self.pending_prompt = False
        if self.state == 'alarm':
            self._transition(timestamp, 'engaged', 'attentiveness_response')
        self.last_attentiveness_reset = timestamp

    def _disengage(self, timestamp, trigger):
        self._transition(timestamp, 'disengaged', trigger)
        self.pending_prompt = False
        self.prompt_time = None
        self.last_attentiveness_reset = None

    def _process_sensor(self, event):
        t = event['timestamp']
        sensor_type = event['sensor_type'].lower()
        data_value = event['data_value']

        if sensor_type == 'lidar':
            if data_value < EMERGENCY_BRAKE_THRESHOLD:
                self._add_command(t, 'BrakingSystem', 'brake')
                self._add_decision(t, 'emergency braking', 'BRAKE')
            else:
                self._add_decision(t, 'emergency braking', 'no brake')

            if self.state in ('engaged', 'alarm'):
                if data_value < 20.0:
                    speed_adj = round(data_value - 20.0, 4)
                else:
                    speed_adj = 0.0
                self._add_command(t, 'Engine', speed_adj)
                self._add_decision(t, 'cruise control', speed_adj)

        elif sensor_type == 'camera':
            if self.state in ('engaged', 'alarm'):
                correction = round(-data_value, 4)
                self._add_command(t, 'SteeringWheel', correction)
                self._add_decision(t, 'lane keeping', correction)

    def _process_driver_event(self, event):
        t = event['timestamp']
        event_type = event['event_type'].lower()
        value = event['value']

        if event_type == 'engage':
            if self.state == 'disengaged':
                self._transition(t, 'engaged', 'engage')
                self.last_attentiveness_reset = t
                self.pending_prompt = False

        elif event_type == 'disengage':
            if self.state != 'disengaged':
                self._disengage(t, 'disengage')

        elif event_type == 'steering_wheel_force':
            if value > FORCE_DISENGAGE_THRESHOLD:
                if self.state != 'disengaged':
                    self._disengage(t, 'steering_wheel_force')
            elif self.pending_prompt:
                if value <= FORCE_VALID_THRESHOLD:
                    self._handle_valid_attentiveness_response(t)
                # between 3N and 10N: ignored

    def process_events(self, events):
        for event in events:
            self._check_time_events(event['timestamp'])
            if event['source'] == 'sensor':
                self._process_sensor(event)
            else:
                self._process_driver_event(event)


def read_sensor_log(filepath):
    events = []
    with open(filepath, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            events.append({
                'source': 'sensor',
                'timestamp': float(row['timestamp']),
                'sensor_id': row['sensor_id'],
                'sensor_type': row['sensor_type'],
                'data_value': float(row['data_value']),
                'unit': row['unit'],
            })
    return events


def read_driver_events(filepath):
    events = []
    with open(filepath, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            events.append({
                'source': 'driver',
                'timestamp': float(row['timestamp']),
                'event_type': row['event_type'],
                'value': float(row['value']),
            })
    return events


def write_csv(filepath, fieldnames, rows):
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description='Copilot driver assistance system')
    parser.add_argument('--input', required=True, help='Input directory')
    parser.add_argument('--output', required=True, help='Output directory')
    args = parser.parse_args()

    sensor_events = read_sensor_log(os.path.join(args.input, 'sensor_log.csv'))
    driver_events = read_driver_events(os.path.join(args.input, 'driver_events.csv'))

    # Driver events first in ties so driver intent takes priority
    all_events = driver_events + sensor_events
    all_events.sort(key=lambda e: e['timestamp'])

    copilot = Copilot()
    copilot.process_events(all_events)

    os.makedirs(args.output, exist_ok=True)

    write_csv(
        os.path.join(args.output, 'state_log.csv'),
        ['timestamp', 'previous_state', 'current_state', 'trigger_event'],
        copilot.state_log,
    )
    write_csv(
        os.path.join(args.output, 'commands_log.csv'),
        ['timestamp', 'actuator_id', 'values'],
        copilot.commands_log,
    )
    write_csv(
        os.path.join(args.output, 'feature_decision.csv'),
        ['timestamp', 'feature', 'decision'],
        copilot.feature_decisions,
    )


if __name__ == '__main__':
    main()
