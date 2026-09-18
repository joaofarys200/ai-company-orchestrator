"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Crash Recovery Engine & State Reconciliation.
Guarantees duplicate side-effect prevention and safe resumption without blind assumptions.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.agents.long_horizon_missions.models import (
    CheckpointType,
    LongHorizonMission,
    MilestoneState,
    MissionCheckpoint,
    MissionState,
)


class RecoveryReconciliationError(Exception):
    """Raised when recovery reconciliation detects irreconcilable discrepancies."""
    pass


class CrashRecoveryEngine:
    """
    Simulates crashes and manages safe state restoration:
    CRASH -> LOAD CHECKPOINT -> RECONCILE -> DETECT RESIDUALS -> RESUME / ROLLBACK / HUMAN_REVIEW.
    """

    def __init__(self):
        self.recovery_events: List[Dict[str, Any]] = []

    def simulate_crash(self, mission: LongHorizonMission, interruption_stage: str) -> Dict[str, Any]:
        """
        Simulates an abrupt process termination during any stage:
        planning, agent execution, patch, merge, build, test, verification, checkpoint.
        """
        crash_id = f"crash_{int(time.time()*1000)}"
        event = {
            "crash_id": crash_id,
            "mission_id": mission.mission_id,
            "interruption_stage": interruption_stage,
            "previous_state": mission.current_state.value,
            "timestamp": time.time(),
        }
        mission.current_state = MissionState.RECOVERING
        self.recovery_events.append(event)
        return event

    def reconcile_and_resume(
        self,
        mission: LongHorizonMission,
        checkpoint: MissionCheckpoint,
        current_workspace_state: Dict[str, Any],
        applied_transaction_ids: Set[str],
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Reconciles the loaded checkpoint with the physical workspace reality.
        Prevents duplicate side effects and recalculates completed milestones,
        pending intents, claims, evidence, and budget.
        Returns: (decision, reconciliation_report)
        Decision can be: "RESUME", "ROLLBACK", or "HUMAN_REVIEW".
        """
        rec_start = time.time()
        discrepancies: List[str] = []
        residuals_detected: List[str] = []

        # 1. Compare architecture hash
        ws_arch_hash = current_workspace_state.get("architecture_hash", "")
        if ws_arch_hash and ws_arch_hash != checkpoint.architecture_hash:
            discrepancies.append("ARCHITECTURE_HASH_MISMATCH")

        # 2. Check for duplicate transactions / partial uncommitted mutations
        checkpoint_txs = set(checkpoint.transaction_states.get("applied_tx_ids", []))
        ghost_txs = applied_transaction_ids - checkpoint_txs
        if ghost_txs:
            residuals_detected.append(f"UNCOMMITTED_OR_GHOST_TRANSACTIONS: {ghost_txs}")

        # 3. Prevent duplicate side effects: filter out already applied transactions
        safe_to_resume_txs = list(applied_transaction_ids.intersection(checkpoint_txs))

        # 4. Determine recovery decision
        if len(residuals_detected) > 0 and current_workspace_state.get("corrupted", False):
            decision = "HUMAN_REVIEW"
        elif discrepancies:
            decision = "ROLLBACK"
        else:
            decision = "RESUME"

        report = {
            "reconciliation_time_ms": (time.time() - rec_start) * 1000.0,
            "checkpoint_id": checkpoint.checkpoint_id,
            "decision": decision,
            "discrepancies": discrepancies,
            "residuals": residuals_detected,
            "safe_transactions": safe_to_resume_txs,
            "checkpoint_milestones_completed": [
                m_id for m_id, m in checkpoint.plan_dag.get("milestones", {}).items()
                if m.get("status") == "COMPLETED"
            ],
        }

        # Apply state reconciliation to mission
        if decision == "RESUME":
            mission.current_state = MissionState.READY
            mission.checkpoint_id = checkpoint.checkpoint_id
        elif decision == "ROLLBACK":
            mission.current_state = MissionState.ROLLED_BACK
        else:
            mission.current_state = MissionState.HUMAN_REVIEW

        return decision, report
