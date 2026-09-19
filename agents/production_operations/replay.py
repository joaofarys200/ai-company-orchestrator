"""
Phase 71 — Deterministic Incident Replay Engine
Reconstructs operational states, decisions, and outcomes from ledger logs without side effects.
Produces REPLAY_MATCH or REPLAY_DIVERGENCE.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from .models import LedgerEntry, OperationalState
from .state_machine import OperationalStateMachine


class IncidentReplayer:
    """
    Simulates operational timeline execution from ledger events without invoking external system calls.
    """

    def __init__(self, service_id: str):
        self.service_id = service_id

    def replay(self, entries: List[LedgerEntry]) -> Tuple[str, List[Dict[str, Any]], str]:
        """
        Replays the ledger entries through the deterministic state machine.
        Returns (status, reconstructed_steps, explanation).
        status is either 'REPLAY_MATCH' or 'REPLAY_DIVERGENCE'.
        """
        if not entries:
            return "REPLAY_MATCH", [], "Empty ledger replayed with 0 divergence."

        reconstructed_steps: List[Dict[str, Any]] = []
        try:
            initial_state = OperationalState(entries[0].state_before)
        except ValueError:
            initial_state = OperationalState.READY_FOR_OPERATIONS

        sm = OperationalStateMachine(initial_state=initial_state)

        for idx, entry in enumerate(entries):
            expected_before = entry.state_before
            expected_after = entry.state_after

            # Check that current state matches expected before
            if sm.current_state.value != expected_before:
                return (
                    "REPLAY_DIVERGENCE",
                    reconstructed_steps,
                    f"Divergence at entry {idx} ({entry.event_id}): "
                    f"state machine was at {sm.current_state.value}, but entry expects {expected_before}."
                )

            # Check transition legality
            try:
                target_state = OperationalState(expected_after)
                sm.transition_to(target_state, reason=f"Replay action: {entry.action}")
            except Exception as exc:
                return (
                    "REPLAY_DIVERGENCE",
                    reconstructed_steps,
                    f"Transition failed at entry {idx} ({entry.event_id}): {str(exc)}"
                )

            reconstructed_steps.append({
                "step_index": idx,
                "event_id": entry.event_id,
                "state_before": expected_before,
                "action": entry.action,
                "state_after": expected_after,
                "entry_hash": entry.entry_hash,
            })

        return "REPLAY_MATCH", reconstructed_steps, f"All {len(entries)} ledger events replayed deterministically without divergence."
