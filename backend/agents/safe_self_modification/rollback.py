"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: rollback.py
Executes deterministic, cryptographically verified rollback restoring pre-modification snapshots.
Strictly requires CURRENT_HASHES == SNAPSHOT_HASHES to declare ROLLED_BACK.
Detects partial failures and residual state, routing incomplete restorations to HUMAN_REVIEW.
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from .models import ModificationTransaction, RollbackResult, TransactionalSnapshot, TransactionState


class RollbackEngine:
    """Restores workspace to immutable snapshot state and cryptographically verifies cleanliness."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.getcwd()

    def execute_rollback(
        self,
        transaction: ModificationTransaction,
        snapshot: TransactionalSnapshot,
        reason: str = "Rollback triggered",
    ) -> RollbackResult:
        """Restore all files recorded in the snapshot and verify hashes match 100%."""
        t0 = time.time()
        logs: List[str] = [f"ROLLBACK_INITIATED: Reason: {reason}"]
        restored_files: List[str] = []
        residual_changes: List[str] = []

        try:
            for rel_path, orig_hash in snapshot.files_state.items():
                abs_path = os.path.join(self.workspace_root, rel_path) if not os.path.isabs(rel_path) else rel_path

                if orig_hash == "FILE_DOES_NOT_EXIST":
                    # File was newly created during the transaction; delete it to cleanly rollback
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                        logs.append(f"ROLLBACK_REMOVED_NEW_FILE: Deleted {rel_path}")
                        restored_files.append(rel_path)
                else:
                    # Restore original content
                    orig_content = snapshot.file_contents.get(rel_path, "")
                    parent_dir = os.path.dirname(abs_path)
                    if parent_dir and not os.path.exists(parent_dir):
                        os.makedirs(parent_dir, exist_ok=True)

                    with open(abs_path, "w", encoding="utf-8", newline="") as f:
                        f.write(orig_content)

                    # Verify restored hash
                    with open(abs_path, "rb") as f:
                        curr_hash = hashlib.sha256(f.read()).hexdigest()

                    if curr_hash != orig_hash:
                        residual_changes.append(rel_path)
                        logs.append(f"HASH_MISMATCH: Restored hash {curr_hash[:8]} != expected {orig_hash[:8]} for {rel_path}")
                    else:
                        restored_files.append(rel_path)
                        logs.append(f"RESTORED_AND_VERIFIED: {rel_path} (hash: {orig_hash[:8]})")

            hash_verification_passed = len(residual_changes) == 0
            success = hash_verification_passed

            duration_ms = round((time.time() - t0) * 1000, 3)

            if success:
                logs.append("ROLLBACK_VERIFIED: CURRENT_HASHES == SNAPSHOT_HASHES confirmed across all files.")
                transaction.transition_to(TransactionState.ROLLED_BACK, reason=reason)
            else:
                logs.append(f"RESIDUAL_STATE_DETECTED: {len(residual_changes)} files have residual changes. Escalating to HUMAN_REVIEW.")
                transaction.residual_changes = residual_changes
                transaction.transition_to(TransactionState.HUMAN_REVIEW, reason="Residual state post-rollback")

            return RollbackResult(
                success=success,
                restored_files=restored_files,
                hash_verification_passed=hash_verification_passed,
                residual_changes=residual_changes,
                logs=logs,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logs.append(f"ROLLBACK_FATAL_ERROR: {e}")
            transaction.transition_to(TransactionState.HUMAN_REVIEW, reason=f"Rollback exception: {e}")
            return RollbackResult(
                success=False,
                restored_files=restored_files,
                hash_verification_passed=False,
                residual_changes=[str(e)],
                logs=logs,
                duration_ms=round((time.time() - t0) * 1000, 3),
            )
