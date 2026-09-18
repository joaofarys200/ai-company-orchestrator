"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: intent.py
Validates and manages AgentEngineeringIntent lifecycle transitions.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from .models import AgentEngineeringIntent, IntentState


class IntentManager:
    """Oversees proposal, validation, and lifecycle transitions of engineering intents."""

    VALID_TRANSITIONS: Dict[IntentState, List[IntentState]] = {
        IntentState.PROPOSED: [IntentState.VALIDATED, IntentState.ABORTED],
        IntentState.VALIDATED: [IntentState.CLAIMED, IntentState.WAITING, IntentState.CONFLICTED, IntentState.ABORTED],
        IntentState.CLAIMED: [IntentState.RUNNING, IntentState.WAITING, IntentState.ABORTED, IntentState.CONFLICTED],
        IntentState.WAITING: [IntentState.CLAIMED, IntentState.RUNNING, IntentState.CONFLICTED, IntentState.ABORTED],
        IntentState.RUNNING: [IntentState.COMPLETED, IntentState.CONFLICTED, IntentState.ROLLED_BACK, IntentState.ABORTED],
        IntentState.CONFLICTED: [IntentState.WAITING, IntentState.CLAIMED, IntentState.ABORTED, IntentState.ROLLED_BACK],
        IntentState.COMPLETED: [],
        IntentState.ABORTED: [],
        IntentState.ROLLED_BACK: [],
    }

    def __init__(self):
        self.intents: Dict[str, AgentEngineeringIntent] = {}

    def register_intent(self, intent: AgentEngineeringIntent) -> Tuple[bool, str]:
        """Validate and record a proposed engineering intent."""
        if not intent.agent_id:
            return False, "INVALID_INTENT: agent_id is required."
        if not intent.intent_id:
            return False, "INVALID_INTENT: intent_id is required."
        if not intent.requested_files and not intent.requested_symbols and not intent.requested_contracts:
            return False, "INVALID_INTENT: Intent must request at least one file, symbol, or contract."

        intent.state = IntentState.PROPOSED
        self.intents[intent.intent_id] = intent
        return True, f"INTENT_REGISTERED: {intent.intent_id} recorded in PROPOSED state."

    def validate_intent(self, intent_id: str) -> Tuple[bool, str]:
        """Validate semantic structure and transition to VALIDATED."""
        intent = self.intents.get(intent_id)
        if not intent:
            return False, f"INTENT_NOT_FOUND: {intent_id}"

        if intent.state != IntentState.PROPOSED:
            return False, f"INVALID_STATE: Cannot validate intent in {intent.state} state."

        intent.state = IntentState.VALIDATED
        return True, f"INTENT_VALIDATED: {intent_id} is structurally valid."

    def transition_state(self, intent_id: str, new_state: IntentState, reason: str = "") -> Tuple[bool, str]:
        """Transition intent state enforcing valid state machine rules."""
        intent = self.intents.get(intent_id)
        if not intent:
            return False, f"INTENT_NOT_FOUND: {intent_id}"

        curr = intent.state
        allowed = self.VALID_TRANSITIONS.get(curr, [])
        if new_state not in allowed:
            return False, f"ILLEGAL_TRANSITION: Cannot transition {curr} -> {new_state} for {intent_id}. Reason: {reason}"

        intent.state = new_state
        return True, f"TRANSITION_SUCCESS: {intent_id} {curr} -> {new_state}. Reason: {reason}"

    def get_intent(self, intent_id: str) -> Optional[AgentEngineeringIntent]:
        return self.intents.get(intent_id)

    def list_active_intents(self) -> List[AgentEngineeringIntent]:
        return [
            it for it in self.intents.values()
            if it.state in {IntentState.PROPOSED, IntentState.VALIDATED, IntentState.CLAIMED, IntentState.WAITING, IntentState.RUNNING, IntentState.CONFLICTED}
        ]
