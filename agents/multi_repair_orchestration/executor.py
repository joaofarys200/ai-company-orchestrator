"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Transactional Repair Executor.
Executes planned repair sequences step-by-step with pre-repair checkpoints and immediate
incremental verification.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from agents.multi_repair_orchestration.checkpoint import RepairCheckpointManager
from agents.multi_repair_orchestration.models import (
    ConvergenceState,
    FailureItem,
    RepairTransaction,
    RevealedFailureType,
    TransactionStatus,
    compute_deterministic_hash,
)
from agents.multi_repair_orchestration.validator import IncrementalRepairValidator


class TransactionalRepairExecutor:
    """
    Executes repairs transactionally, ensuring that every modification is checkpointed
    and incrementally verified before advancing to the next step.
    """

    def __init__(
        self,
        checkpoint_manager: Optional[RepairCheckpointManager] = None,
        incremental_validator: Optional[IncrementalRepairValidator] = None,
    ):
        self.checkpoint_manager = checkpoint_manager or RepairCheckpointManager()
        self.incremental_validator = incremental_validator or IncrementalRepairValidator()

    def execute_transaction(
        self,
        transaction: RepairTransaction,
        target_files: List[str],
        fail_at_step: Optional[int] = None,
        simulate_revealed_failure: bool = False,
    ) -> Tuple[bool, str, List[FailureItem]]:
        transaction.status = TransactionStatus.EXECUTING

        # Capture initial state hash
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

        transaction.state_before_hash = compute_deterministic_hash(current_state)

        revealed_failures: List[FailureItem] = []

        for idx, candidate in enumerate(transaction.repairs):
            cand_id = getattr(candidate, "repair_id", f"rep_{idx}")

            # 1. Create Pre-repair checkpoint
            chk = self.checkpoint_manager.create_checkpoint(
                transaction_id=transaction.transaction_id,
                step_index=idx,
                repair_id=cand_id,
                target_files=target_files,
                patch_hash=compute_deterministic_hash(str(candidate)),
                verification_result="PRE_APPLY",
            )
            transaction.checkpoints.append(chk)

            # 2. Check for simulated failure injection
            if fail_at_step is not None and idx == fail_at_step:
                transaction.status = TransactionStatus.FAILED
                return False, f"STEP_FAILED_AT_INDEX_{idx}", revealed_failures

            # 3. Apply Patch
            diffs = getattr(candidate, "diffs", [])
            for diff in diffs:
                fpath = getattr(diff, "file_path", "")
                if fpath:
                    os.makedirs(os.path.dirname(os.path.abspath(fpath)), exist_ok=True)
                    # Simple append or replacement simulation
                    added = getattr(diff, "added_lines", [])
                    if added:
                        content = "\n".join(added) + "\n"
                        with open(fpath, "a", encoding="utf-8") as f:
                            f.write(content)

            # 4. Incremental Verification
            val_res = self.incremental_validator.validate_step(candidate, target_files)
            if not val_res.get("success", False):
                transaction.status = TransactionStatus.FAILED
                return False, f"INCREMENTAL_VALIDATION_FAILED_STEP_{idx}", revealed_failures

            # 5. Check if repair reveals a hidden secondary failure
            if simulate_revealed_failure and idx == 0:
                rev_fail = FailureItem(
                    failure_id=f"fail_revealed_{idx}",
                    error_class="ReferenceError",
                    symbol="authToken",
                    file_path=target_files[0] if target_files else "unknown.js",
                    line=42,
                    message="authToken is not defined in secondary route",
                    failure_type=RevealedFailureType.REVEALED_FAILURE,
                    revealed_by_repair_id=cand_id,
                )
                revealed_failures.append(rev_fail)
                transaction.revealed_failures.append(rev_fail)

        # Re-compute after hash
        after_state: Dict[str, str] = {}
        for fpath in target_files:
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        after_state[fpath] = f.read()
                except Exception:
                    after_state[fpath] = ""
            else:
                after_state[fpath] = "__FILE_DOES_NOT_EXIST__"

        transaction.state_after_hash = compute_deterministic_hash(after_state)
        transaction.status = TransactionStatus.COMMITTED
        return True, "TRANSACTION_EXECUTED", revealed_failures
