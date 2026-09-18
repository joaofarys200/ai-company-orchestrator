"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: apply.py
Performs transactional application of patches to the filesystem with strict safety guards.
Disallows direct uncontrolled disk mutations outside active transactions.
"""

from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

from .models import ModificationPatch, ModificationTransaction, TransactionState


class TransactionalApplier:
    """Safely applies patches to workspace within an active transaction."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.getcwd()

    def apply_patch(
        self,
        transaction: ModificationTransaction,
        patch: ModificationPatch,
    ) -> Tuple[bool, List[str]]:
        """Write modified contents to disk under transactional governance."""
        logs: List[str] = []

        if transaction.current_state != TransactionState.APPLYING:
            return (
                False,
                [f"APPLY_FAILED: Transaction state must be APPLYING, got {transaction.current_state.value}"],
            )

        applied_files: List[str] = []
        try:
            for rel_path, new_content in patch.new_contents.items():
                abs_path = os.path.join(self.workspace_root, rel_path) if not os.path.isabs(rel_path) else rel_path

                # Ensure parent directory exists
                parent_dir = os.path.dirname(abs_path)
                if parent_dir and not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)
                    logs.append(f"CREATED_DIR: {parent_dir}")

                with open(abs_path, "w", encoding="utf-8", newline="") as f:
                    f.write(new_content)

                applied_files.append(rel_path)
                logs.append(f"APPLIED_FILE: Wrote {len(new_content)} bytes to {rel_path}")

            transaction.patches.append(patch)
            logs.append(f"APPLY_SUCCESS: Successfully applied {len(applied_files)} files in patch {patch.patch_id}.")
            return True, logs

        except Exception as e:
            logs.append(f"APPLY_EXCEPTION: Failed applying patch: {e}")
            return False, logs
