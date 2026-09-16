"""
JARVIS OS — Phase 56: Crash Recovery Engine
Recovers governance state, ledger, and checkpoint consistency after abrupt process crashes.
"""

from __future__ import annotations

import time
from typing import Dict, Any, List, Optional, Tuple
from agents.repair_convergence_governance.models import (
    ConvergenceState,
    RepairStepSnapshot,
    TerminationBudget,
    TerminationState,
)
from agents.repair_convergence_governance.ledger import ProgressLedger


class CrashRecoveryEngine:
    """Restores transaction governance state after unhandled process termination or crash."""

    def __init__(self):
        pass

    def recover_from_persistence(
        self,
        persisted_ledger_entries: List[Dict[str, Any]],
        persisted_checkpoint_hash: str,
        persisted_budget: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ConvergenceState, ProgressLedger, TerminationBudget]:
        """Rebuilds the active governance state from serialized ledger records."""
        ledger = ProgressLedger()
        for item in persisted_ledger_entries:
            ledger.append_entry(
                event_type=item.get("event_type", "recovered_event"),
                payload=item.get("payload", {})
            )

        budget = TerminationBudget()
        if persisted_budget:
            budget.consumed_repairs = persisted_budget.get("consumed_repairs", 0)
            budget.consumed_runtime = persisted_budget.get("consumed_runtime", 0.0)
            budget.consumed_rollbacks = persisted_budget.get("consumed_rollbacks", 0)

        # Recover last known state
        last_entry = persisted_ledger_entries[-1] if persisted_ledger_entries else {}
        last_payload = last_entry.get("payload", {})

        raw_state = last_payload.get("state", TerminationState.UNKNOWN.value)
        try:
            state_enum = TerminationState(raw_state)
        except ValueError:
            state_enum = TerminationState.UNKNOWN

        recovered_state = ConvergenceState(
            state=state_enum,
            iteration=last_payload.get("iteration", len(persisted_ledger_entries)),
            failure_count=last_payload.get("failure_count", 0),
            blocking_failure_count=last_payload.get("blocking", 0),
            risk_score=last_payload.get("risk", 0.0),
            coverage=last_payload.get("coverage", 0.0),
            uncertainty=last_payload.get("uncertainty", 0.0),
            proof_status=last_payload.get("proof_status", "RECOVERED"),
            repair_count=last_payload.get("repair_count", 0),
            state_hash=persisted_checkpoint_hash,
            previous_state_hash=last_payload.get("previous_hash", ""),
        )

        return recovered_state, ledger, budget

    def revalidate_unknown_state(
        self,
        state: ConvergenceState,
        active_failures_probe: List[str],
        invariants_verified: bool,
    ) -> ConvergenceState:
        """Enforces mandatory revalidation rule: unknown state cannot proceed blindly."""
        if state.state == TerminationState.UNKNOWN:
            if invariants_verified and len(active_failures_probe) == 0:
                state.state = TerminationState.STABLE
            elif len(active_failures_probe) > 0:
                state.state = TerminationState.CONVERGING
            else:
                state.state = TerminationState.FAILED
            state.failure_count = len(active_failures_probe)
        return state
