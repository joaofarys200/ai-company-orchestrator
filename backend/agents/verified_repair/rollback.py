"""
JARVIS OS — Phase 54: Repair Rollback Engine
Executes atomic restoration to snapshot state and cryptographically verifies state equivalence.
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

from agents.verified_repair.models import (
    RepairCandidate,
    compute_deterministic_hash,
)
from agents.verified_repair.patch import PatchManager


class RepairRollbackEngine:
    """
    Executes verifiable, non-destructive rollbacks.
    Guarantees that state_after_rollback_hash == state_before_hash.
    """

    def __init__(self) -> None:
        self.patch_manager = PatchManager()

    def execute_rollback(
        self,
        candidate: RepairCandidate,
        workspace_dir: str,
        expected_before_hash: str,
    ) -> Tuple[bool, str, str]:
        """
        Restores files from candidate.rollback_plan['snapshots'] and proves equivalence.
        Returns: (verified, after_rollback_hash, message)
        """
        snapshots: Dict[str, str] = candidate.rollback_plan.get("snapshots", {})
        if not snapshots:
            return False, "", "Plano de rollback não possui snapshots válidos."

        try:
            for rel_path, original_content in snapshots.items():
                abs_path = os.path.join(workspace_dir, rel_path)
                if original_content:
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.write(original_content)
                elif os.path.exists(abs_path):
                    os.remove(abs_path)

            after_rollback_hash = self.patch_manager.compute_state_hash(workspace_dir, candidate.files)
            verified = (after_rollback_hash == expected_before_hash)

            if verified:
                msg = f"Rollback verificado com sucesso: {after_rollback_hash} == {expected_before_hash}"
            else:
                msg = f"Divergência pós-rollback: obtido {after_rollback_hash} != esperado {expected_before_hash}"

            return verified, after_rollback_hash, msg

        except Exception as e:
            return False, "", f"Erro durante execução do rollback: {e}"
