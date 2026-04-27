"""Processing engine: orchestrates the perception, decision, and actuator layers."""
from __future__ import annotations

from pathlib import Path
from typing import Union

from actuator import write_commands_log, write_feature_decisions, write_state_log
from decision import CopilotStateMachine
from models import DriverEvent, SensorEvent
from perception import load_all_events


class CopilotEngine:
    """Top-level orchestrator for one simulation run."""

    def __init__(self, input_dir: Path, output_dir: Path) -> None:
        self.input_dir = input_dir
        self.output_dir = output_dir
        self._sm = CopilotStateMachine()

    def run(self) -> None:
        """Execute the full pipeline: load → process → write outputs."""
        print(f"[Copilot] Loading events from: {self.input_dir}")
        events = load_all_events(self.input_dir)
        total = len(events)
        print(f"[Copilot] {total} event(s) loaded — processing...")

        for idx, event in enumerate(events, 1):
            desc = _describe(event)
            print(f"[Copilot] [{idx}/{total}] {desc}")
            self._sm.process_event(event)
            print(f"[Copilot]          state → {self._sm.current_state.value}")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Copilot] Writing outputs to: {self.output_dir}")

        write_state_log(self.output_dir, self._sm.state_log)
        write_commands_log(self.output_dir, self._sm.commands_log)
        write_feature_decisions(self.output_dir, self._sm.feature_decisions)

        print("[Copilot] Complete.")
        print(f"[Copilot]   Final state      : {self._sm.current_state.value}")
        print(f"[Copilot]   State transitions: {len(self._sm.state_log)}")
        print(f"[Copilot]   Commands issued  : {len(self._sm.commands_log)}")
        print(f"[Copilot]   Feature decisions: {len(self._sm.feature_decisions)}")


def _describe(event: Union[SensorEvent, DriverEvent]) -> str:
    if isinstance(event, DriverEvent):
        suffix = f" force={event.value}" if event.value is not None else ""
        return f"DriverEvent  t={event.timestamp:>6}  {event.event_type.value}{suffix}"
    return (f"SensorEvent  t={event.timestamp:>6}  {event.sensor_type.value}"
            f"  value={event.data_value}")
