"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: transaction.py
Finite State Machine managing the lifecycle of an architecture modification transaction.
Strictly disallows invalid or skipped state transitions (e.g. PREFLIGHT -> COMMITTED).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import ModificationTransaction, TransactionState


class TransactionEngine:
    """Manages transactional state transitions and history for self-modification."""

    # Valid State Machine Transitions
    ALLOWED_TRANSITIONS: Dict[TransactionState, Set[TransactionState]] = {
        TransactionState.CREATED: {
            TransactionState.PREFLIGHT,
            TransactionState.FAILED,
            TransactionState.BLOCKED,
        },
        TransactionState.PREFLIGHT: {
            TransactionState.SNAPSHOTTED,
            TransactionState.FAILED,
            TransactionState.BLOCKED,
        },
        TransactionState.SNAPSHOTTED: {
            TransactionState.PLANNED,
            TransactionState.FAILED,
            TransactionState.ROLLING_BACK,
        },
        TransactionState.PLANNED: {
            TransactionState.PATCHING,
            TransactionState.FAILED,
            TransactionState.ROLLING_BACK,
            TransactionState.HUMAN_REVIEW,
        },
        TransactionState.PATCHING: {
            TransactionState.PATCH_VALIDATED,
            TransactionState.FAILED,
            TransactionState.ROLLING_BACK,
        },
        TransactionState.PATCH_VALIDATED: {
            TransactionState.APPLYING,
            TransactionState.FAILED,
            TransactionState.ROLLING_BACK,
            TransactionState.BLOCKED,
        },
        TransactionState.APPLYING: {
            TransactionState.APPLIED,
            TransactionState.ROLLING_BACK,
            TransactionState.FAILED,
        },
        TransactionState.APPLIED: {
            TransactionState.BUILDING,
            TransactionState.ROLLING_BACK,
            TransactionState.FAILED,
        },
        TransactionState.BUILDING: {
            TransactionState.TESTING,
            TransactionState.ROLLING_BACK,
            TransactionState.FAILED,
        },
        TransactionState.TESTING: {
            TransactionState.VERIFYING,
            TransactionState.ROLLING_BACK,
            TransactionState.FAILED,
            TransactionState.HUMAN_REVIEW,
        },
        TransactionState.VERIFYING: {
            TransactionState.ARCHITECTURE_RESCANNING,
            TransactionState.ROLLING_BACK,
            TransactionState.FAILED,
            TransactionState.HUMAN_REVIEW,
        },
        TransactionState.ARCHITECTURE_RESCANNING: {
            TransactionState.COMMIT_READY,
            TransactionState.ROLLING_BACK,
            TransactionState.FAILED,
            TransactionState.HUMAN_REVIEW,
        },
        TransactionState.COMMIT_READY: {
            TransactionState.COMMITTED,
            TransactionState.ROLLING_BACK,
            TransactionState.HUMAN_REVIEW,
            TransactionState.BLOCKED,
        },
        TransactionState.ROLLING_BACK: {
            TransactionState.ROLLED_BACK,
            TransactionState.FAILED,
            TransactionState.HUMAN_REVIEW,
        },
        # Terminal states
        TransactionState.COMMITTED: set(),
        TransactionState.ROLLED_BACK: set(),
        TransactionState.FAILED: {TransactionState.ROLLING_BACK},
        TransactionState.BLOCKED: {TransactionState.ROLLING_BACK, TransactionState.HUMAN_REVIEW},
        TransactionState.HUMAN_REVIEW: {
            TransactionState.ROLLING_BACK,
            TransactionState.COMMITTED,
            TransactionState.APPLYING,
        },
    }

    def __init__(self):
        self.transactions: Dict[str, ModificationTransaction] = {}

    def create_transaction(
        self,
        transaction_id: str,
        governance_decision_id: str,
        parent_transaction_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ModificationTransaction:
        """Instantiate a new modification transaction in CREATED state."""
        tx = ModificationTransaction(
            transaction_id=transaction_id,
            parent_transaction_id=parent_transaction_id,
            governance_decision_id=governance_decision_id,
            current_state=TransactionState.CREATED,
            metadata=metadata or {},
            created_at=time.time(),
            updated_at=time.time(),
        )
        tx.state_history.append({
            "from_state": "NONE",
            "to_state": TransactionState.CREATED.value,
            "reason": "Transaction initialized",
            "timestamp": time.time(),
        })
        self.transactions[transaction_id] = tx
        return tx

    def transition(
        self,
        transaction_id: str,
        target_state: TransactionState,
        reason: str = "",
    ) -> Tuple[bool, str]:
        """Perform validated transition from current state to target state."""
        tx = self.transactions.get(transaction_id)
        if not tx:
            return False, f"TRANSACTION_ERROR: Transaction '{transaction_id}' not found."

        allowed = self.ALLOWED_TRANSITIONS.get(tx.current_state, set())
        if target_state not in allowed:
            return (
                False,
                f"INVALID_TRANSITION: Cannot transition from {tx.current_state.value} to {target_state.value}. "
                f"Allowed: {[s.value for s in allowed]}",
            )

        tx.transition_to(target_state, reason=reason)
        return True, f"TRANSITION_SUCCESS: Moved to {target_state.value} ({reason})"
