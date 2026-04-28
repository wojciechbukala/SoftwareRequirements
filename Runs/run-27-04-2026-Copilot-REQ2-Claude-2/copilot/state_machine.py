"""
State machine: defines operating states and the runtime context maintained by Copilot.

States (FR-01):
  Disengaged      – autonomous features inactive; emergency braking still live.
  Engaged         – full autonomous operation active.
  AwaitingResponse– waiting for a driver attentiveness response (up to 5 s).
  Alarming        – continuous alarm active; awaiting driver acknowledgement.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class State(Enum):
    """The four operating modes of the Copilot system."""

    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"


@dataclass
class CopilotContext:
    """Mutable runtime context shared across all processing layers.

    Attributes:
        state:               Current operating mode.
        last_prompt_time:    Timestamp (s) when the most recent attentiveness
                             prompt was issued, or when Engaged mode was entered.
                             None until the system first enters Engaged mode.
        awaiting_start_time: Timestamp (s) when AwaitingResponse was entered.
                             None when not in that state.
    """

    state: State = State.DISENGAGED
    last_prompt_time: Optional[float] = None
    awaiting_start_time: Optional[float] = None
