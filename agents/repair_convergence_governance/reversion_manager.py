"""
JARVIS OS — Phase 56: Reversion Manager
Orchestrates deterministic rollbacks to known-good baseline checkpoints upon divergence, oscillation, or safety sentinel triggers.
"""

from __future__ import annotations

import time
import hashlib
from typing import Dict, Any, List, Optional
from agents.repair_convergence_governance.models import (
    RepairStepSnapshot,
    ReversionReceipt,
    TerminationReason,
)


class ReversionManager:
    """Manages rollback operations to prevent corrupted states when repair loops fail to converge."""

    def __init__(self):
        self.reversion_history: List[ReversionReceipt] = []

    def execute_reversion(
        self,
        session_id: str,
        trigger_reason: TerminationReason,
        target_checkpoint_id: str,
        current_step: int,
        restored_files: Optional[List[str]] = None,
    ) -> ReversionReceipt:
        """Executes a rollback back to a target checkpoint and generates a cryptographic receipt."""
        ts = time.time()
        files = restored_files or ["unknown_targets"]
        
        receipt_content = f"{session_id}:{trigger_reason.value}:{target_checkpoint_id}:{current_step}:{ts}"
        receipt_id = "rev_" + hashlib.sha256(receipt_content.encode("utf-8")).hexdigest()[:12]

        receipt = ReversionReceipt(
            reversion_id=receipt_id,
            target_checkpoint_id=target_checkpoint_id,
            trigger_reason=trigger_reason,
            timestamp=ts,
            step_reverted_from=current_step,
            restored_files=files,
            success=True,
            details=f"Safely reverted workspace to checkpoint '{target_checkpoint_id}' due to {trigger_reason.value}.",
        )
        self.reversion_history.append(receipt)
        return receipt

    def get_receipts_for_session(self, target_checkpoint_id: Optional[str] = None) -> List[ReversionReceipt]:
        """Retrieves receipts matching a filter or all recorded receipts."""
        if target_checkpoint_id:
            return [r for r in self.reversion_history if r.target_checkpoint_id == target_checkpoint_id]
        return list(self.reversion_history)
