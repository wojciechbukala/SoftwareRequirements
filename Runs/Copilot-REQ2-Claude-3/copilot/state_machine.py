"""
State machine — core decision-control logic for the Copilot system.

States
------
* Disengaged      — system is off; default initial state.
* Engaged         — system actively assisting; 120 s attentiveness timer active.
* AwaitingResponse — prompted the driver; waiting up to 5 s for a response.
* Alarming        — driver did not respond in time; alarm is active.

State transitions are governed by:
- Explicit driver events (ENGAGE, DISENGAGE, STEERING_FORCE).
- Time-based rules checked at every incoming event via
  :meth:`StateMachine.check_time_transitions`.

All state changes are appended to :attr:`StateMachine.transitions` as
immutable :class:`StateTransition` records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from copilot.actuator import ActuatorCommand


# ---------------------------------------------------------------------------
# State enumeration
# ---------------------------------------------------------------------------

class State(str, Enum):
    """Exhaustive set of system states."""

    DISENGAGED = "Disengaged"
    ENGAGED = "Engaged"
    AWAITING_RESPONSE = "AwaitingResponse"
    ALARMING = "Alarming"


# ---------------------------------------------------------------------------
# Transition record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StateTransition:
    """
    An immutable record of a single state change.

    Attributes:
        timestamp:      When the transition occurred (event timestamp).
        previous_state: The state before the transition.
        current_state:  The state after the transition.
        trigger_event:  Human-readable label for the cause.
    """

    timestamp: float
    previous_state: str
    current_state: str
    trigger_event: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROMPT_INTERVAL_S: float = 120.0   # seconds between attentiveness prompts
RESPONSE_TIMEOUT_S: float = 5.0    # seconds driver has to respond
STEERING_FORCE_DISENGAGE: float = 10.0   # > this → Disengaged (FR-04)
STEERING_FORCE_ENGAGE: float = 3.0       # ≤ this → Engaged from Awaiting/Alarming


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class StateMachine:
    """
    Manages system state and emits :class:`StateTransition` records.

    The machine also accumulates :class:`~copilot.actuator.ActuatorCommand`
    objects for time-triggered actions (prompt, alarm) so the event loop can
    collect them alongside the normal command pipeline.

    Attributes:
        current_state:           Active state.
        transitions:             Ordered list of all recorded transitions.
        pending_commands:        Commands emitted by time-triggered transitions
                                 (drained by the event loop after each event).
        _last_prompt_ts:         Timestamp of the most recent attentiveness prompt.
        _awaiting_since_ts:      Timestamp when AwaitingResponse was entered.
    """

    def __init__(self) -> None:
        self.current_state: State = State.DISENGAGED
        self.transitions: list[StateTransition] = []
        self.pending_commands: list[ActuatorCommand] = []

        # Timer bookkeeping
        self._last_prompt_ts: float | None = None
        self._awaiting_since_ts: float | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_transition(
        self,
        timestamp: float,
        previous: State,
        new: State,
        trigger: str,
    ) -> None:
        """
        Append a :class:`StateTransition` and update :attr:`current_state`.

        Only records the transition if *previous* != *new* (safety guard;
        callers should also check before calling to avoid duplicate records).
        """
        if previous == new:
            return
        self.transitions.append(
            StateTransition(
                timestamp=timestamp,
                previous_state=previous.value,
                current_state=new.value,
                trigger_event=trigger,
            )
        )
        self.current_state = new

    def _enter_engaged(self, timestamp: float) -> None:
        """Reset the 120 s attentiveness timer when entering Engaged state."""
        self._last_prompt_ts = timestamp
        self._awaiting_since_ts = None

    def _enter_awaiting(self, timestamp: float) -> None:
        """Record the time at which AwaitingResponse was entered."""
        self._awaiting_since_ts = timestamp

    # ------------------------------------------------------------------
    # Time-based transition checks (PF-02)
    # ------------------------------------------------------------------

    def check_time_transitions(self, timestamp: float) -> None:
        """
        Evaluate timer-based rules using *timestamp* as the current clock.

        Must be called **before** dispatching each event in the event loop.

        Rules checked:
        1. While Engaged and ≥ 120 s since last prompt → AwaitingResponse
           and emit an attentiveness prompt command.
        2. While AwaitingResponse and ≥ 5 s with no valid response → Alarming
           and emit an alarm command.

        Args:
            timestamp: The current event's timestamp in seconds.
        """
        # Deferred import to avoid circular dependency at module load time.
        from copilot.actuator import prompt_command, alarm_command

        if self.current_state == State.ENGAGED:
            if (
                self._last_prompt_ts is not None
                and (timestamp - self._last_prompt_ts) >= PROMPT_INTERVAL_S
            ):
                prev = self.current_state
                self._enter_awaiting(timestamp)
                self._record_transition(
                    timestamp, prev, State.AWAITING_RESPONSE, "120s_prompt_interval"
                )
                self.pending_commands.append(prompt_command(timestamp))

        elif self.current_state == State.AWAITING_RESPONSE:
            if (
                self._awaiting_since_ts is not None
                and (timestamp - self._awaiting_since_ts) >= RESPONSE_TIMEOUT_S
            ):
                prev = self.current_state
                self._record_transition(
                    timestamp, prev, State.ALARMING, "5s_response_timeout"
                )
                self.pending_commands.append(alarm_command(timestamp))

    # ------------------------------------------------------------------
    # Event-driven transition handlers
    # ------------------------------------------------------------------

    def handle_engage(self, timestamp: float) -> None:
        """
        Process an ENGAGE driver event.

        Transition: Disengaged → Engaged.
        No-op if the system is already in any other state.

        Args:
            timestamp: Event timestamp in seconds.
        """
        if self.current_state != State.DISENGAGED:
            return  # ENGAGE only meaningful from Disengaged
        prev = self.current_state
        self._enter_engaged(timestamp)
        self._record_transition(timestamp, prev, State.ENGAGED, "ENGAGE")

    def handle_disengage(self, timestamp: float) -> None:
        """
        Process a DISENGAGE driver event.

        Transition: any non-Disengaged state → Disengaged.

        Args:
            timestamp: Event timestamp in seconds.
        """
        if self.current_state == State.DISENGAGED:
            return
        prev = self.current_state
        self._record_transition(timestamp, prev, State.DISENGAGED, "DISENGAGE")

    def handle_steering_force(self, timestamp: float, force: float) -> None:
        """
        Process a STEERING_FORCE driver event and apply force-based rules.

        Rules (evaluated in priority order):
        * force > 10 N  → Disengaged (from any state).
        * AwaitingResponse / Alarming and force ≤ 3 N → Engaged (reset timer).
        * AwaitingResponse and 3 N < force < 10 N     → ignored.

        Args:
            timestamp: Event timestamp in seconds.
            force:     Steering wheel force in Newtons.
        """
        if force > STEERING_FORCE_DISENGAGE:
            if self.current_state != State.DISENGAGED:
                prev = self.current_state
                self._record_transition(
                    timestamp, prev, State.DISENGAGED, "STEERING_FORCE>10N"
                )
            return

        if self.current_state in (State.AWAITING_RESPONSE, State.ALARMING):
            if force <= STEERING_FORCE_ENGAGE:
                prev = self.current_state
                self._enter_engaged(timestamp)
                self._record_transition(
                    timestamp, prev, State.ENGAGED, "STEERING_FORCE<=3N"
                )
            # 3 N < force < 10 N while AwaitingResponse → intentionally ignored
