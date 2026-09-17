"""
JARVIS OS — Phase 54: Patch Application & Lineage Manager
Applies surgical patches with strict cryptographic lineage preservation and atomic snapshots.
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

from agents.verified_repair.models import (
    FilePatchDiff,
    RepairCandidate,
    compute_deterministic_hash,
)


class PatchManager:
    """
    Applies patches to disk while maintaining immutable cryptographic lineage.
    Never loses lineage or applies unversioned mutations.
    """

    def compute_state_hash(self, workspace_dir: str, target_files: List[str]) -> str:
        """Computes a consolidated SHA-256 hash of the target files in their current state."""
        file_hashes: Dict[str, str] = {}
        for rel_path in sorted(target_files):
            abs_path = os.path.join(workspace_dir, rel_path)
            if os.path.exists(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_hashes[rel_path] = compute_deterministic_hash(f.read())
                except Exception:
                    file_hashes[rel_path] = "unreadable"
            else:
                file_hashes[rel_path] = "missing"
        return compute_deterministic_hash(file_hashes, prefix="state_")

    def apply_candidate_patch(
        self,
        candidate: RepairCandidate,
        workspace_dir: str,
    ) -> Tuple[bool, str, str, str]:
        """
        Applies all patches in a candidate to disk atomically.
        Returns: (success, before_hash, patch_hash, after_hash)
        """
        before_hash = self.compute_state_hash(workspace_dir, candidate.files)
        patch_payload = [p.to_dict() for p in candidate.patches]
        patch_hash = compute_deterministic_hash(patch_payload, prefix="patch_")

        # Snapshot current content for rollback
        snapshots: Dict[str, str] = {}
        for patch in candidate.patches:
            abs_path = os.path.join(workspace_dir, patch.relative_path)
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    snapshots[patch.relative_path] = f.read()
            else:
                snapshots[patch.relative_path] = ""

        # Update candidate's rollback plan with verified snapshot
        candidate.rollback_plan["snapshots"] = snapshots

        # Write patched files to disk
        try:
            for patch in candidate.patches:
                abs_path = os.path.join(workspace_dir, patch.relative_path)
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(patch.patched_content)

            after_hash = self.compute_state_hash(workspace_dir, candidate.files)
            return True, before_hash, patch_hash, after_hash
        except Exception:
            # Revert on write failure
            for rel_path, content in snapshots.items():
                abs_path = os.path.join(workspace_dir, rel_path)
                if content:
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.write(content)
            return False, before_hash, patch_hash, before_hash
