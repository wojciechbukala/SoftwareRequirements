import unittest
import os
import csv
from unittest.mock import patch, mock_open

from constants import (
    SENSOR_LOG_HEADERS, DRIVER_EVENTS_HEADERS, STATE_LOG_HEADERS,
    COMMANDS_LOG_HEADERS, FEATURE_DECISION_HEADERS,
    SystemState, SensorType, DriverEventType, ActuatorID, Feature,
    EMERGENCY_BRAKING_DISTANCE_M, ATTENTIVENESS_PROMPT_INTERVAL_S,
    ATTENTIVENESS_RESPONSE_WINDOW_S, ATTENTIVENESS_VALID_RESPONSE_FORCE_N,
    DRIVER_OVERRIDE_FORCE_N
)
from csv_utils import read_csv, write_csv
from data_models import SensorEvent, DriverEvent, MergedEvent
from copilot_logic import Copilot
from copilot import parse_sensor_event, parse_driver_event # Import parsing functions from copilot.py

class TestCsvUtils(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_data"
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_file = os.path.join(self.test_dir, "test.csv")
        self.headers = ["col1", "col2"]
        self.data = [
            {"col1": "val1a", "col2": "val1b"},
            {"col1": "val2a", "col2": "val2b"}
        ]

    def tearDown(self):
        if os.path.exists(self.test_dir):
            import shutil
            shutil.rmtree(self.test_dir)

    def test_write_csv_and_read_csv(self):
        write_csv(self.test_file, self.headers, self.data)
        read_data = read_csv(self.test_file, self.headers)
        self.assertEqual(read_data, self.data)

    def test_read_csv_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            read_csv("non_existent_file.csv", self.headers)

    def test_read_csv_incorrect_headers(self):
        incorrect_headers_file = os.path.join(self.test_dir, "incorrect_headers.csv")
        with open(incorrect_headers_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["wrong1", "wrong2"])
            writer.writerow(["val", "val"])
        with self.assertRaisesRegex(ValueError, "incorrect headers"):
            read_csv(incorrect_headers_file, self.headers)

class TestDataModels(unittest.TestCase):
    def test_merged_event_sorting(self):
        event1 = MergedEvent(timestamp=10.0, event_type="sensor", data=SensorEvent(10.0, "s1", SensorType.LIDAR, 5.0, "m"))
        event2 = MergedEvent(timestamp=5.0, event_type="driver", data=DriverEvent(5.0, DriverEventType.ENGAGE, "ENGAGE"))
        event3 = MergedEvent(timestamp=15.0, event_type="sensor", data=SensorEvent(15.0, "s2", SensorType.CAMERA, 100.0, "m"))

        sorted_events = sorted([event1, event2, event3])
        self.assertEqual(sorted_events, [event2, event1, event3])

    def test_parse_sensor_event(self):
        row = {"timestamp": "1.0", "sensor_id": "L1", "sensor_type": "LIDAR", "data_value": "10.5", "unit": "m"}
        event = parse_sensor_event(row)
        self.assertEqual(event.timestamp, 1.0)
        self.assertEqual(event.sensor_type, SensorType.LIDAR)
        self.assertEqual(event.data_value, 10.5)

    def test_parse_driver_event(self):
        row_force = {"timestamp": "2.0", "event_type": "STEERING_FORCE", "value": "7.5"}
        event_force = parse_driver_event(row_force)
        self.assertEqual(event_force.timestamp, 2.0)
        self.assertEqual(event_force.event_type, DriverEventType.STEERING_FORCE)
        self.assertEqual(event_force.value, 7.5)

        row_engage = {"timestamp": "3.0", "event_type": "ENGAGE", "value": "ENGAGE"}
        event_engage = parse_driver_event(row_engage)
        self.assertEqual(event_engage.timestamp, 3.0)
        self.assertEqual(event_engage.event_type, DriverEventType.ENGAGE)
        self.assertEqual(event_engage.value, "ENGAGE")

class TestCopilotLogic(unittest.TestCase):
    def setUp(self):
        self.copilot = Copilot()

    def test_initial_state(self):
        self.assertEqual(self.copilot.state, SystemState.DISENGAGED)
        self.assertEqual(len(self.copilot.state_log), 1) # Initial state log

    def test_engage_disengage(self):
        # Engage
        self.copilot.process_event(1.0, DriverEvent(1.0, DriverEventType.ENGAGE, "ENGAGE"))
        self.assertEqual(self.copilot.state, SystemState.ENGAGED)
        self.assertEqual(len(self.copilot.state_log), 2)
        self.assertEqual(self.copilot.state_log[-1].current_state, SystemState.ENGAGED)

        # Disengage
        self.copilot.process_event(2.0, DriverEvent(2.0, DriverEventType.DISENGAGE, "DISENGAGE"))
        self.assertEqual(self.copilot.state, SystemState.DISENGAGED)
        self.assertEqual(len(self.copilot.state_log), 3)
        self.assertEqual(self.copilot.state_log[-1].current_state, SystemState.DISENGAGED)

    def test_emergency_braking(self):
        # Lidar < 5m triggers braking regardless of state
        self.copilot.process_event(1.0, SensorEvent(1.0, "L1", SensorType.LIDAR, EMERGENCY_BRAKING_DISTANCE_M - 0.1, "m"))
        self.assertEqual(len(self.copilot.commands_log), 1)
        self.assertEqual(self.copilot.commands_log[-1].actuator_id, ActuatorID.BRAKING_SYSTEM)
        self.assertEqual(self.copilot.commands_log[-1].value, "APPLY_BRAKE")
        self.assertEqual(len(self.copilot.feature_decision_log), 1)
        self.assertEqual(self.copilot.feature_decision_log[-1].feature, Feature.EMERGENCY_BRAKING)
        self.assertEqual(self.copilot.feature_decision_log[-1].decision, "BRAKING")

        # Lidar >= 5m does not trigger braking
        self.copilot.process_event(2.0, SensorEvent(2.0, "L1", SensorType.LIDAR, EMERGENCY_BRAKING_DISTANCE_M + 0.1, "m"))
        self.assertEqual(len(self.copilot.commands_log), 1) # Still 1, no new brake command
        self.assertEqual(len(self.copilot.feature_decision_log), 2)
        self.assertEqual(self.copilot.feature_decision_log[-1].decision, "NON_BRAKING")

    def test_attentiveness_flow(self):
        # Engage system
        self.copilot.process_event(0.0, DriverEvent(0.0, DriverEventType.ENGAGE, "ENGAGE"))
        self.assertEqual(self.copilot.state, SystemState.ENGAGED)

        # Time passes, prompt should be issued
        self.copilot.process_event(ATTENTIVENESS_PROMPT_INTERVAL_S + 0.1, SensorEvent(ATTENTIVENESS_PROMPT_INTERVAL_S + 0.1, "C1", SensorType.CAMERA, 10.0, "m"))
        self.assertEqual(self.copilot.state, SystemState.AWAITING_RESPONSE)
        self.assertIn(CommandLogEntry(ATTENTIVENESS_PROMPT_INTERVAL_S + 0.1, ActuatorID.STEERING_MOTOR, "SMALL_MOVEMENT"), self.copilot.commands_log)

        # Valid response within window
        self.copilot.process_event(ATTENTIVENESS_PROMPT_INTERVAL_S + ATTENTIVENESS_RESPONSE_WINDOW_S - 1.0, DriverEvent(ATTENTIVENESS_PROMPT_INTERVAL_S + ATTENTIVENESS_RESPONSE_WINDOW_S - 1.0, DriverEventType.STEERING_FORCE, ATTENTIVENESS_VALID_RESPONSE_FORCE_N - 0.1))
        self.assertEqual(self.copilot.state, SystemState.ENGAGED)

        # Prompt again
        self.copilot.process_event(ATTENTIVENESS_PROMPT_INTERVAL_S * 2 + 0.1, SensorEvent(ATTENTIVENESS_PROMPT_INTERVAL_S * 2 + 0.1, "C1", SensorType.CAMERA, 10.0, "m"))
        self.assertEqual(self.copilot.state, SystemState.AWAITING_RESPONSE)

        # No response, timeout to Alarming
        self.copilot.process_event(ATTENTIVENESS_PROMPT_INTERVAL_S * 2 + ATTENTIVENESS_RESPONSE_WINDOW_S + 0.1, SensorEvent(ATTENTIVENESS_PROMPT_INTERVAL_S * 2 + ATTENTIVENESS_RESPONSE_WINDOW_S + 0.1, "C1", SensorType.CAMERA, 10.0, "m"))
        self.assertEqual(self.copilot.state, SystemState.ALARMING)
        self.assertIn(CommandLogEntry(ATTENTIVENESS_PROMPT_INTERVAL_S * 2 + ATTENTIVENESS_RESPONSE_WINDOW_S + 0.1, ActuatorID.ALARM, "CONTINUOUS_ALARM"), self.copilot.commands_log)

        # Clear alarm with response
        self.copilot.process_event(ATTENTIVENESS_PROMPT_INTERVAL_S * 2 + ATTENTIVENESS_RESPONSE_WINDOW_S + 5.0, DriverEvent(ATTENTIVENESS_PROMPT_INTERVAL_S * 2 + ATTENTIVENESS_RESPONSE_WINDOW_S + 5.0, DriverEventType.STEERING_FORCE, ATTENTIVENESS_VALID_RESPONSE_FORCE_N - 0.1))
        self.assertEqual(self.copilot.state, SystemState.ENGAGED)

    def test_driver_override(self):
        # Engage system
        self.copilot.process_event(0.0, DriverEvent(0.0, DriverEventType.ENGAGE, "ENGAGE"))
        self.assertEqual(self.copilot.state, SystemState.ENGAGED)

        # Driver override in ENGAGED state
        self.copilot.process_event(10.0, DriverEvent(10.0, DriverEventType.STEERING_FORCE, DRIVER_OVERRIDE_FORCE_N + 0.1))
        self.assertEqual(self.copilot.state, SystemState.DISENGAGED)
        self.assertEqual(self.copilot.state_log[-1].trigger_event, "Driver override (force > 10N)")

        # Engage again
        self.copilot.process_event(20.0, DriverEvent(20.0, DriverEventType.ENGAGE, "ENGAGE"))
        self.copilot.process_event(ATTENTIVENESS_PROMPT_INTERVAL_S + 20.1, SensorEvent(ATTENTIVENESS_PROMPT_INTERVAL_S + 20.1, "C1", SensorType.CAMERA, 10.0, "m"))
        self.assertEqual(self.copilot.state, SystemState.AWAITING_RESPONSE)

        # Driver override in AWAITING_RESPONSE state
        self.copilot.process_event(ATTENTIVENESS_PROMPT_INTERVAL_S + 25.0, DriverEvent(ATTENTIVENESS_PROMPT_INTERVAL_S + 25.0, DriverEventType.STEERING_FORCE, DRIVER_OVERRIDE_FORCE_N + 0.1))
        self.assertEqual(self.copilot.state, SystemState.DISENGAGED)

    def test_lane_keeping_cruise_control(self):
        self.copilot.process_event(0.0, DriverEvent(0.0, DriverEventType.ENGAGE, "ENGAGE"))
        self.copilot.process_event(1.0, SensorEvent(1.0, "C1", SensorType.CAMERA, 50.0, "m"))

        self.assertEqual(self.copilot.state, SystemState.ENGAGED)
        self.assertEqual(len(self.copilot.feature_decision_log), 2) # Lane Keeping, Cruise Control
        self.assertEqual(self.copilot.feature_decision_log[-2].feature, Feature.LANE_KEEPING)
        self.assertAlmostEqual(self.copilot.feature_decision_log[-2].decision, 5.0) # 50.0 * 0.1
        self.assertEqual(self.copilot.feature_decision_log[-1].feature, Feature.CRUISE_CONTROL)
        self.assertAlmostEqual(self.copilot.feature_decision_log[-1].decision, 2.5) # 50.0 * 0.05
        
        self.assertEqual(len(self.copilot.commands_log), 2) # Steering Motor, Steering Motor (for speed)
        self.assertEqual(self.copilot.commands_log[-2].actuator_id, ActuatorID.STEERING_MOTOR)
        self.assertAlmostEqual(self.copilot.commands_log[-2].value, 5.0)
        self.assertEqual(self.copilot.commands_log[-1].actuator_id, ActuatorID.STEERING_MOTOR)
        self.assertAlmostEqual(self.copilot.commands_log[-1].value, 2.5)

    def test_disengaged_mode_no_commands(self):
        # Initial state is Disengaged
        self.copilot.process_event(1.0, SensorEvent(1.0, "C1", SensorType.CAMERA, 50.0, "m"))
        # Should only log feature decision for camera if in engaged state
        self.assertEqual(len(self.copilot.feature_decision_log), 0) # Only initial state log
        self.assertEqual(len(self.copilot.commands_log), 0)

        # Trigger emergency braking in Disengaged - should still work
        self.copilot.process_event(2.0, SensorEvent(2.0, "L1", SensorType.LIDAR, EMERGENCY_BRAKING_DISTANCE_M - 0.1, "m"))
        self.assertEqual(len(self.copilot.commands_log), 1)
        self.assertEqual(self.copilot.commands_log[-1].actuator_id, ActuatorID.BRAKING_SYSTEM)
        self.assertEqual(len(self.copilot.feature_decision_log), 1)
        self.assertEqual(self.copilot.feature_decision_log[-1].feature, Feature.EMERGENCY_BRAKING)


if __name__ == "__main__":
    unittest.main()
