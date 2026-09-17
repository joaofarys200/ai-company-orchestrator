"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Transactional Rollback Engine.
Provides atomic partial rollback (to last safe checkpoint) and atomic global rollback
(to original transaction state) with strict cryptographic hash verification.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from agents.multi_repair_orchestration.checkpoint import RepairCheckpointManager
from agents.multi_repair_orchestration.models import (
    RepairCheckpoint,
    RepairTransaction,
    TransactionStatus,
    compute_deterministic_hash,
)


class TransactionalRollbackEngine:
    """
    Executes and verifies atomic rollbacks at both partial (single-step) and global (transaction) boundaries.
    """

    def __init__(self, checkpoint_manager: Optional[RepairCheckpointManager] = None):
        self.checkpoint_manager = checkpoint_manager or RepairCheckpointManager()

    def rollback_to_checkpoint(
        self,
        transaction: RepairTransaction,
        checkpoint_id: str,
        target_files: List[str],
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Rollback to a specific intermediate checkpoint, reverting subsequent changes
        while preserving prior verified repairs.
        """
        chk = next((c for c in transaction.checkpoints if c.checkpoint_id == checkpoint_id), None)
        if not chk:
            return False, "CHECKPOINT_NOT_FOUND", {}

        success = self.checkpoint_manager.restore_checkpoint(chk)
        if not success:
            return False, "RESTORE_FAILED", {}

        # Re-compute current state hash
        current_state: Dict[str, str] = {}
        for fpath in target_files:
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        current_state[fpath] = f.read()
                except Exception:
                    current_state[fpath] = ""
            else:
                current_state[fpath] = "__FILE_DOES_NOT_EXIST__"

        current_hash = compute_deterministic_hash(current_state)
        hash_verified = (current_hash == chk.state_hash)

        audit_entry = {
            "type": "PARTIAL_ROLLBACK",
            "checkpoint_id": checkpoint_id,
            "expected_state_hash": chk.state_hash,
            "restored_state_hash": current_hash,
            "hash_verified": hash_verified,
            "step_index": chk.step_index,
        }
        transaction.rollback_lineage.append(audit_entry)

        return hash_verified, "SUCCESS" if hash_verified else "HASH_MISMATCH", audit_entry

    def rollback_global(
        self,
        transaction: RepairTransaction,
        initial_snapshot: Dict[str, str],
        target_files: List[str],
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Rollback the entire transaction to the original state before any repair was applied.
        """
        try:
            for fpath, content in initial_snapshot.items():
                if content == "__FILE_DOES_NOT_EXIST__":
                    if os.path.exists(fpath):
                        os.remove(fpath)
                else:
                    os.makedirs(os.path.dirname(os.path.abspath(fpath)), exist_ok=True)
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(content)
        except Exception as e:
            return False, f"RESTORE_ERROR: {str(e)}", {}

        current_state: Dict[str, str] = {}
        for fpath in target_files:
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        current_state[fpath] = f.read()
                except Exception:
                    current_state[fpath] = ""
            else:
                current_state[fpath] = "__FILE_DOES_NOT_EXIST__"

        restored_hash = compute_deterministic_hash(current_state)
        expected_hash = transaction.state_before_hash
        hash_verified = (restored_hash == expected_hash)

        transaction.status = TransactionStatus.ROLLED_BACK

        audit_entry = {
            "type": "GLOBAL_ROLLBACK",
            "transaction_id": transaction.transaction_id,
            "before_hash": expected_hash,
            "restored_hash": restored_hash,
            "hash_verified": hash_verified,
        }
        transaction.rollback_lineage.append(audit_entry)

        return hash_verified, "SUCCESS" if hash_verified else "HASH_MISMATCH", audit_entry
