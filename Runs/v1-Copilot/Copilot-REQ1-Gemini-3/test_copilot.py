import unittest
import os
import csv
from datetime import datetime, timedelta
import shutil
from copilot import Copilot, EventProcessor, STATE_DISENGAGED, STATE_ENGAGED, STATE_ALARM

class TestCopilot(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_run"
        self.input_dir = os.path.join(self.test_dir, "input")
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        self.sensor_log_path = os.path.join(self.input_dir, "sensor_log.csv")
        self.driver_events_path = os.path.join(self.input_dir, "driver_events.csv")
        self.state_log_path = os.path.join(self.output_dir, "state_log.csv")
        self.commands_log_path = os.path.join(self.output_dir, "commands_log.csv")
        self.feature_decision_path = os.path.join(self.output_dir, "feature_decision.csv")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _write_sensor_log(self, data):
        with open(self.sensor_log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "sensor_id", "sensor_type", "data_value", "unit"])
            for row in data:
                writer.writerow(row)

    def _write_driver_events(self, data):
        with open(self.driver_events_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "event_type", "value"])
            for row in data:
                writer.writerow(row)

    def _read_csv(self, file_path):
        data = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        return data

    def test_initial_state_and_engage_disengage(self):
        start_time = datetime(2026, 5, 8, 10, 0, 0)
        sensor_data = [
            [(start_time + timedelta(seconds=1)).isoformat(), "s1", "CAMERA", "100", "pixels"],
        ]
        driver_events = [
            [(start_time + timedelta(seconds=2)).isoformat(), "ENGAGE_BUTTON_PRESS", ""],
            [(start_time + timedelta(seconds=3)).isoformat(), "DISENGAGE_BUTTON_PRESS", ""],
        ]
        self._write_sensor_log(sensor_data)
        self._write_driver_events(driver_events)

        copilot = Copilot(self.input_dir, self.output_dir)
        event_processor = EventProcessor(self.input_dir)

        while True:
            next_event = event_processor.get_next_event()
            if not next_event:
                break
            timestamp, event_type, event_data = next_event
            copilot.process_event(event_type, event_data)
        copilot._close_output_files()

        state_log = self._read_csv(self.state_log_path)
        self.assertEqual(len(state_log), 2)
        self.assertEqual(state_log[0]["previous_state"], STATE_DISENGAGED)
        self.assertEqual(state_log[0]["current_state"], STATE_ENGAGED)
        self.assertEqual(state_log[0]["trigger_event"], "Engage_Button_Press")
        self.assertEqual(state_log[1]["previous_state"], STATE_ENGAGED)
        self.assertEqual(state_log[1]["current_state"], STATE_DISENGAGED)
        self.assertEqual(state_log[1]["trigger_event"], "Disengage_Button_Press")

    def test_emergency_braking(self):
        start_time = datetime(2026, 5, 8, 10, 0, 0)
        sensor_data = [
            [(start_time + timedelta(seconds=1)).isoformat(), "s1", "LIDAR", "10.0", "m"],
            [(start_time + timedelta(seconds=2)).isoformat(), "s2", "LIDAR", "4.5", "m"], # Emergency brake
            [(start_time + timedelta(seconds=3)).isoformat(), "s3", "LIDAR", "6.0", "m"],
        ]
        driver_events = []
        self._write_sensor_log(sensor_data)
        self._write_driver_events(driver_events)

        copilot = Copilot(self.input_dir, self.output_dir)
        event_processor = EventProcessor(self.input_dir)

        while True:
            next_event = event_processor.get_next_event()
            if not next_event:
                break
            timestamp, event_type, event_data = next_event
            copilot.process_event(event_type, event_data)
        copilot._close_output_files()

        commands_log = self._read_csv(self.commands_log_path)
        feature_decision_log = self._read_csv(self.feature_decision_path)

        self.assertEqual(len(commands_log), 1)
        self.assertEqual(commands_log[0]["actuator_id"], "BRAKING_SYSTEM")
        self.assertEqual(commands_log[0]["values"], "BRAKE")

        self.assertEqual(len(feature_decision_log), 1)
        self.assertEqual(feature_decision_log[0]["feature"], "EMERGENCY_BRAKING")
        self.assertEqual(feature_decision_log[0]["decision"], "BRAKE")
        
        state_log = self._read_csv(self.state_log_path)
        self.assertEqual(len(state_log), 0) # No state change for emergency braking

    def test_high_steering_force_disengagement(self):
        start_time = datetime(2026, 5, 8, 10, 0, 0)
        sensor_data = []
        driver_events = [
            [(start_time + timedelta(seconds=1)).isoformat(), "ENGAGE_BUTTON_PRESS", ""],
            [(start_time + timedelta(seconds=2)).isoformat(), "STEERING_WHEEL_FORCE", "12.0"], # High force
        ]
        self._write_sensor_log(sensor_data)
        self._write_driver_events(driver_events)

        copilot = Copilot(self.input_dir, self.output_dir)
        event_processor = EventProcessor(self.input_dir)

        while True:
            next_event = event_processor.get_next_event()
            if not next_event:
                break
            timestamp, event_type, event_data = next_event
            copilot.process_event(event_type, event_data)
        copilot._close_output_files()

        state_log = self._read_csv(self.state_log_path)
        self.assertEqual(len(state_log), 2)
        self.assertEqual(state_log[0]["current_state"], STATE_ENGAGED)
        self.assertEqual(state_log[1]["current_state"], STATE_DISENGAGED)
        self.assertEqual(state_log[1]["trigger_event"], "High_Steering_Force_Disengagement")

    def test_attentiveness_check_valid_response(self):
        start_time = datetime(2026, 5, 8, 10, 0, 0)
        sensor_data = []
        driver_events = [
            [(start_time + timedelta(seconds=1)).isoformat(), "ENGAGE_BUTTON_PRESS", ""],
            [(start_time + timedelta(seconds=121)).isoformat(), "SENSOR_READING", "dummy"], # Trigger attentiveness check
            [(start_time + timedelta(seconds=122)).isoformat(), "STEERING_WHEEL_FORCE", "2.0"], # Valid response
        ]
        self._write_sensor_log(sensor_data)
        self._write_driver_events(driver_events)

        copilot = Copilot(self.input_dir, self.output_dir)
        event_processor = EventProcessor(self.input_dir)

        while True:
            next_event = event_processor.get_next_event()
            if not next_event:
                break
            timestamp, event_type, event_data = next_event
            copilot.process_event(event_type, event_data)
        copilot._close_output_files()

        state_log = self._read_csv(self.state_log_path)
        commands_log = self._read_csv(self.commands_log_path)

        self.assertEqual(len(state_log), 1) # Only engage
        self.assertEqual(state_log[0]["current_state"], STATE_ENGAGED)

        self.assertEqual(len(commands_log), 1)
        self.assertEqual(commands_log[0]["actuator_id"], "STEERING_WHEEL")
        self.assertEqual(commands_log[0]["values"], "SMALL_MOVEMENT")

    def test_attentiveness_check_ignored_response_then_timeout(self):
        start_time = datetime(2026, 5, 8, 10, 0, 0)
        sensor_data = []
        driver_events = [
            [(start_time + timedelta(seconds=1)).isoformat(), "ENGAGE_BUTTON_PRESS", ""],
            [(start_time + timedelta(seconds=121)).isoformat(), "SENSOR_READING", "dummy"], # Trigger attentiveness check
            [(start_time + timedelta(seconds=122)).isoformat(), "STEERING_WHEEL_FORCE", "5.0"], # Ignored response
            [(start_time + timedelta(seconds=127)).isoformat(), "SENSOR_READING", "dummy"], # After timeout window
        ]
        self._write_sensor_log(sensor_data)
        self._write_driver_events(driver_events)

        copilot = Copilot(self.input_dir, self.output_dir)
        event_processor = EventProcessor(self.input_dir)

        while True:
            next_event = event_processor.get_next_event()
            if not next_event:
                break
            timestamp, event_type, event_data = next_event
            copilot.process_event(event_type, event_data)
        copilot._close_output_files()

        state_log = self._read_csv(self.state_log_path)
        commands_log = self._read_csv(self.commands_log_path)
        
        self.assertEqual(len(state_log), 2) # Engage -> Alarm
        self.assertEqual(state_log[0]["current_state"], STATE_ENGAGED)
        self.assertEqual(state_log[1]["current_state"], STATE_ALARM)
        self.assertEqual(state_log[1]["trigger_event"], "Attentiveness_Timeout")

        self.assertEqual(len(commands_log), 1)
        self.assertEqual(commands_log[0]["actuator_id"], "STEERING_WHEEL")
        self.assertEqual(commands_log[0]["values"], "SMALL_MOVEMENT")

    def test_attentiveness_check_no_response_timeout(self):
        start_time = datetime(2026, 5, 8, 10, 0, 0)
        sensor_data = []
        driver_events = [
            [(start_time + timedelta(seconds=1)).isoformat(), "ENGAGE_BUTTON_PRESS", ""],
            [(start_time + timedelta(seconds=121)).isoformat(), "SENSOR_READING", "dummy"], # Trigger attentiveness check
            [(start_time + timedelta(seconds=127)).isoformat(), "SENSOR_READING", "dummy"], # After timeout window, no response
        ]
        self._write_sensor_log(sensor_data)
        self._write_driver_events(driver_events)

        copilot = Copilot(self.input_dir, self.output_dir)
        event_processor = EventProcessor(self.input_dir)

        while True:
            next_event = event_processor.get_next_event()
            if not next_event:
                break
            timestamp, event_type, event_data = next_event
            copilot.process_event(event_type, event_data)
        copilot._close_output_files()

        state_log = self._read_csv(self.state_log_path)
        commands_log = self._read_csv(self.commands_log_path)

        self.assertEqual(len(state_log), 2) # Engage -> Alarm
        self.assertEqual(state_log[0]["current_state"], STATE_ENGAGED)
        self.assertEqual(state_log[1]["current_state"], STATE_ALARM)
        self.assertEqual(state_log[1]["trigger_event"], "Attentiveness_Timeout")

        self.assertEqual(len(commands_log), 1)
        self.assertEqual(commands_log[0]["actuator_id"], "STEERING_WHEEL")
        self.assertEqual(commands_log[0]["values"], "SMALL_MOVEMENT")

    def test_attentiveness_check_alarm_response_back_to_engaged(self):
        start_time = datetime(2026, 5, 8, 10, 0, 0)
        sensor_data = []
        driver_events = [
            [(start_time + timedelta(seconds=1)).isoformat(), "ENGAGE_BUTTON_PRESS", ""],
            [(start_time + timedelta(seconds=121)).isoformat(), "SENSOR_READING", "dummy"], # Trigger attentiveness check
            [(start_time + timedelta(seconds=127)).isoformat(), "SENSOR_READING", "dummy"], # After timeout window, no response (ALARM)
            [(start_time + timedelta(seconds=128)).isoformat(), "STEERING_WHEEL_FORCE", "1.0"], # Response from ALARM
        ]
        self._write_sensor_log(sensor_data)
        self._write_driver_events(driver_events)

        copilot = Copilot(self.input_dir, self.output_dir)
        event_processor = EventProcessor(self.input_dir)

        while True:
            next_event = event_processor.get_next_event()
            if not next_event:
                break
            timestamp, event_type, event_data = next_event
            copilot.process_event(event_type, event_data)
        copilot._close_output_files()

        state_log = self._read_csv(self.state_log_path)
        self.assertEqual(len(state_log), 3) # Engage -> Alarm -> Engaged
        self.assertEqual(state_log[0]["current_state"], STATE_ENGAGED)
        self.assertEqual(state_log[1]["current_state"], STATE_ALARM)
        self.assertEqual(state_log[1]["trigger_event"], "Attentiveness_Timeout")
        self.assertEqual(state_log[2]["current_state"], STATE_ENGAGED)
        self.assertEqual(state_log[2]["trigger_event"], "Attentiveness_Response")

    def test_engaged_mode_features(self):
        start_time = datetime(2026, 5, 8, 10, 0, 0)
        sensor_data = [
            [(start_time + timedelta(seconds=2)).isoformat(), "s1", "CAMERA", "100", "pixels"],
            [(start_time + timedelta(seconds=3)).isoformat(), "s2", "RADAR", "50", "m"],
        ]
        driver_events = [
            [(start_time + timedelta(seconds=1)).isoformat(), "ENGAGE_BUTTON_PRESS", ""],
        ]
        self._write_sensor_log(sensor_data)
        self._write_driver_events(driver_events)

        copilot = Copilot(self.input_dir, self.output_dir)
        event_processor = EventProcessor(self.input_dir)

        while True:
            next_event = event_processor.get_next_event()
            if not next_event:
                break
            timestamp, event_type, event_data = next_event
            copilot.process_event(event_type, event_data)
        copilot._close_output_files()

        commands_log = self._read_csv(self.commands_log_path)
        feature_decision_log = self._read_csv(self.feature_decision_path)

        self.assertEqual(len(commands_log), 2)
        self.assertEqual(commands_log[0]["actuator_id"], "STEERING_SYSTEM")
        self.assertEqual(commands_log[1]["actuator_id"], "ENGINE_CONTROL")

        self.assertEqual(len(feature_decision_log), 2)
        self.assertEqual(feature_decision_log[0]["feature"], "LANE_KEEPING")
        self.assertEqual(feature_decision_log[1]["feature"], "CRUISE_CONTROL")

if __name__ == "__main__":
    unittest.main()