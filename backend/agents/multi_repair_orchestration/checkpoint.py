"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Repair Checkpoint Manager.
Maintains granular, immutable rollback snapshots before and after each repair step in a transaction.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from agents.multi_repair_orchestration.models import (
    RepairCheckpoint,
    RepairTransaction,
    compute_deterministic_hash,
)


class RepairCheckpointManager:
    """
    Creates and manages granular checkpoints. Preserves full history of snapshots.
    """

    def create_checkpoint(
        self,
        transaction_id: str,
        step_index: int,
        repair_id: str,
        target_files: List[str],
        patch_hash: str,
        verification_result: str,
    ) -> RepairCheckpoint:
        snapshot: Dict[str, str] = {}
        for fpath in target_files:
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        snapshot[fpath] = f.read()
                except Exception:
                    snapshot[fpath] = ""
            else:
                snapshot[fpath] = "__FILE_DOES_NOT_EXIST__"

        state_hash = compute_deterministic_hash(snapshot)
        tree_hash = compute_deterministic_hash(sorted(list(snapshot.keys())))
        checkpoint_id = f"chk_{transaction_id}_{step_index}_{repair_id[:8]}"

        return RepairCheckpoint(
            checkpoint_id=checkpoint_id,
            transaction_id=transaction_id,
            step_index=step_index,
            repair_id=repair_id,
            state_hash=state_hash,
            tree_hash=tree_hash,
            patch_hash=patch_hash,
            verification_result=verification_result,
            rollback_snapshot=snapshot,
        )

    def restore_checkpoint(self, checkpoint: RepairCheckpoint) -> bool:
        """
        Restores the file system state to the snapshot captured in this checkpoint.
        """
        try:
            for fpath, content in checkpoint.rollback_snapshot.items():
                if content == "__FILE_DOES_NOT_EXIST__":
                    if os.path.exists(fpath):
                        os.remove(fpath)
                else:
                    os.makedirs(os.path.dirname(os.path.abspath(fpath)), exist_ok=True)
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(content)
            return True
        except Exception:
            return False
