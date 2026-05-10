import argparse
import csv
import heapq
import os
import sys

# Define system states
STATE_DISENGAGED = "disengaged"
STATE_ENGAGED = "engaged"

# Define event types
EVENT_TYPE_SENSOR = "sensor"
EVENT_TYPE_DRIVER = "driver"
EVENT_TYPE_ATTENTIVENESS_CHECK_PROMPT = "attentiveness_check_prompt"
EVENT_TYPE_ATTENTIVENESS_CHECK_TIMEOUT = "attentiveness_check_timeout"

# Define features
FEATURE_EMERGENCY_BRAKING = "emergency_braking"
FEATURE_LANE_KEEPING = "lane_keeping"
FEATURE_CRUISE_CONTROL = "cruise_control"

class Copilot:
    def __init__(self, output_dir):
        self.current_state = STATE_DISENGAGED
        self.last_attentiveness_check_time = 0.0
        self.attentiveness_check_pending = False
        self.alarm_active = False

        # Output file paths
        self.state_log_path = os.path.join(output_dir, "state_log.csv")
        self.commands_log_path = os.path.join(output_dir, "commands_log.csv")
        self.feature_decision_path = os.path.join(output_dir, "feature_decision.csv")

        # Open output files
        self.state_log_file = open(self.state_log_path, "w", newline="", encoding="utf-8")
        self.commands_log_file = open(self.commands_log_path, "w", newline="", encoding="utf-8")
        self.feature_decision_file = open(self.feature_decision_path, "w", newline="", encoding="utf-8")

        # CSV writers
        self.state_log_writer = csv.writer(self.state_log_file)
        self.commands_log_writer = csv.writer(self.commands_log_file)
        self.feature_decision_writer = csv.writer(self.feature_decision_file)

        # Write headers
        self.state_log_writer.writerow(["timestamp", "previous_state", "current_state", "trigger_event"])
        self.commands_log_writer.writerow(["timestamp", "actuator_id", "values"])
        self.feature_decision_writer.writerow(["timestamp", "feature", "decision"])

    def __del__(self):
        # Close output files
        self.state_log_file.close()
        self.commands_log_file.close()
        self.feature_decision_file.close()

    def log_state_transition(self, timestamp, previous_state, current_state, trigger_event):
        if previous_state != current_state:
            self.state_log_writer.writerow([f"{timestamp:.3f}", previous_state, current_state, trigger_event])

    def log_command(self, timestamp, actuator_id, values):
        self.commands_log_writer.writerow([f"{timestamp:.3f}", actuator_id, values])

    def log_feature_decision(self, timestamp, feature, decision):
        self.feature_decision_writer.writerow([f"{timestamp:.3f}", feature, decision])

    def process_event(self, event):
        timestamp = event["timestamp"]
        event_type = event["event_type"]
        data = event["data"]

        previous_state = self.current_state

        if event_type == EVENT_TYPE_SENSOR:
            sensor_type = data["sensor_type"]
            data_value = data["data_value"]
            unit = data["unit"]

            # Emergency Braking (highest priority, always active)
            if sensor_type == "Lidar" and data_value < 5.0:
                self.log_command(timestamp, "Braking System", "BRAKE")
                self.log_feature_decision(timestamp, FEATURE_EMERGENCY_BRAKING, "BRAKE")

            if self.current_state == STATE_ENGAGED:
                if sensor_type == "Camera":
                    # Lane Keeping (placeholder logic)
                    self.log_command(timestamp, "Steering System", "1.0") # Small steering correction
                    self.log_feature_decision(timestamp, FEATURE_LANE_KEEPING, "KEEP_LANE")
                elif sensor_type == "Speed Sensor":
                    # Cruise Control (placeholder logic)
                    self.log_command(timestamp, "Accelerator System", "5.0") # Maintain speed
                    self.log_feature_decision(timestamp, FEATURE_CRUISE_CONTROL, "MAINTAIN_SPEED")

        elif event_type == EVENT_TYPE_DRIVER:
            driver_event_type = data["event_type"]
            value = data["value"]

            if driver_event_type == "engage_request":
                self.current_state = STATE_ENGAGED
                self.last_attentiveness_check_time = timestamp
                self.attentiveness_check_pending = False
                if self.alarm_active:
                    self.log_command(timestamp, "Alarm System", "OFF")
                    self.alarm_active = False
            elif driver_event_type == "disengage_request":
                self.current_state = STATE_DISENGAGED
                self.attentiveness_check_pending = False
                if self.alarm_active:
                    self.log_command(timestamp, "Alarm System", "OFF")
                    self.alarm_active = False
            elif driver_event_type == "steering_wheel_force":
                # Force > 10 N always disengages
                if value > 10.0:
                    self.current_state = STATE_DISENGAGED
                    self.attentiveness_check_pending = False
                    if self.alarm_active:
                        self.log_command(timestamp, "Alarm System", "OFF")
                        self.alarm_active = False
                    self.log_state_transition(timestamp, previous_state, self.current_state, "steering_wheel_force_disengage")
                    return # Exit early, no further processing for this event

                if self.current_state == STATE_ENGAGED and self.attentiveness_check_pending:
                    if value <= 3.0:
                        # Valid response
                        self.last_attentiveness_check_time = timestamp
                        self.attentiveness_check_pending = False
                        if self.alarm_active:
                            self.log_command(timestamp, "Alarm System", "OFF")
                            self.alarm_active = False
                    elif 3.0 < value <= 10.0:
                        # Ignored response, continue waiting
                        pass
        
        # Log state transition if changed
        self.log_state_transition(timestamp, previous_state, self.current_state, event_type)


def read_csv_file(filepath, event_type):
    events = []
    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader) # Skip header

        for row in reader:
            event = {"timestamp": float(row[0]), "event_type": event_type}
            if event_type == EVENT_TYPE_SENSOR:
                event["data"] = {
                    "sensor_id": row[1],
                    "sensor_type": row[2],
                    "data_value": float(row[3]),
                    "unit": row[4],
                }
            elif event_type == EVENT_TYPE_DRIVER:
                event["data"] = {
                    "event_type": row[1],
                    "value": float(row[2]) if row[2] else 0.0, # Handle empty value for some driver events
                }
            events.append(event)
    return events


def main():
    parser = argparse.ArgumentParser(description="Simulate Copilot driver-assistance system.")
    parser.add_argument("--input", required=True, help="Directory containing input CSV files.")
    parser.add_argument("--output", required=True, help="Directory to write output CSV files.")
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    os.makedirs(output_dir, exist_ok=True)

    sensor_log_path = os.path.join(input_dir, "sensor_log.csv")
    driver_events_path = os.path.join(input_dir, "driver_events.csv")

    all_events = []
    if os.path.exists(sensor_log_path):
        all_events.extend(read_csv_file(sensor_log_path, EVENT_TYPE_SENSOR))
    if os.path.exists(driver_events_path):
        all_events.extend(read_csv_file(driver_events_path, EVENT_TYPE_DRIVER))

    # Sort all events by timestamp
    all_events.sort(key=lambda x: x["timestamp"])

    copilot = Copilot(output_dir)

    # Use a min-heap to manage scheduled events (like attentiveness checks)
    # The heap will store tuples: (timestamp, event_type, event_data)
    scheduled_events_heap = []

    for event in all_events:
        current_time = event["timestamp"]

        # Process scheduled events that are due before the current event
        while scheduled_events_heap and scheduled_events_heap[0][0] <= current_time:
            scheduled_time, scheduled_event_type, scheduled_event_data = heapq.heappop(scheduled_events_heap)
            
            # Create a mock event for scheduled events
            mock_event = {
                "timestamp": scheduled_time,
                "event_type": scheduled_event_type,
                "data": scheduled_event_data
            }
            copilot.process_event(mock_event)

        copilot.process_event(event)

        # Handle attentiveness check scheduling if in engaged mode
        if copilot.current_state == STATE_ENGAGED:
            # Check if it's time for an attentiveness check prompt
            if not copilot.attentiveness_check_pending and (current_time - copilot.last_attentiveness_check_time) >= 120.0:
                copilot.log_command(current_time, "Steering System", "ATTENTIVENESS_PROMPT")
                heapq.heappush(scheduled_events_heap, (current_time + 5.0, EVENT_TYPE_ATTENTIVENESS_CHECK_TIMEOUT, {}))
                copilot.attentiveness_check_pending = True
            
            # Check for attentiveness timeout if pending
            if copilot.attentiveness_check_pending and scheduled_events_heap and scheduled_events_heap[0][1] == EVENT_TYPE_ATTENTIVENESS_CHECK_TIMEOUT and scheduled_events_heap[0][0] <= current_time:
                _, _, _ = heapq.heappop(scheduled_events_heap) # Remove the timeout event
                if copilot.attentiveness_check_pending: # Still pending after current event processing
                    copilot.log_command(current_time, "Alarm System", "ON")
                    copilot.alarm_active = True
                    copilot.attentiveness_check_pending = False # Timeout occurred, no longer waiting for response

    # Process any remaining scheduled events after all main events are done
    while scheduled_events_heap:
        scheduled_time, scheduled_event_type, scheduled_event_data = heapq.heappop(scheduled_events_heap)
        mock_event = {
            "timestamp": scheduled_time,
            "event_type": scheduled_event_type,
            "data": scheduled_event_data
        }
        copilot.process_event(mock_event)


if __name__ == "__main__":
    main()
