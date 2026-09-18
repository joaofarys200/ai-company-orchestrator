"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Checkpoint Management & Cryptographic Snapshot Immutability.
Supports: FULL, MILESTONE, FAILURE, PRE_MUTATION, POST_VERIFICATION.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.long_horizon_missions.models import (
    CheckpointType,
    MissionCheckpoint,
)


class CheckpointTamperError(Exception):
    """Raised when checkpoint hash validation fails."""
    pass


class CheckpointManager:
    """
    Creates, verifies, and stores immutable SHA-256 snapshots across 13 state vectors.
    """

    def __init__(self):
        self._checkpoints: Dict[str, MissionCheckpoint] = {}
        self._checkpoint_chain: List[str] = []

    def create_checkpoint(
        self,
        mission_id: str,
        checkpoint_type: CheckpointType,
        mission_state: str,
        objective_state: Dict[str, Any],
        plan_dag: Dict[str, Any],
        agent_states: Dict[str, Any],
        claims: List[Dict[str, Any]],
        workspace_states: Dict[str, Any],
        transaction_states: Dict[str, Any],
        architecture_hash: str,
        contract_hash: str,
        behavior_hash: str,
        verification_ledger: List[Dict[str, Any]],
        budget_remaining: Dict[str, float],
        evidence_root: str,
        checkpoint_id: Optional[str] = None,
    ) -> MissionCheckpoint:
        cid = checkpoint_id or f"chk_{mission_id}_{int(time.time()*1000)}"
        now = time.time()

        payload = {
            "checkpoint_id": cid,
            "mission_id": mission_id,
            "checkpoint_type": checkpoint_type.value,
            "timestamp": now,
            "mission_state": mission_state,
            "objective_state": objective_state,
            "plan_dag": plan_dag,
            "agent_states": agent_states,
            "claims": claims,
            "workspace_states": workspace_states,
            "transaction_states": transaction_states,
            "architecture_hash": architecture_hash,
            "contract_hash": contract_hash,
            "behavior_hash": behavior_hash,
            "verification_ledger": verification_ledger,
            "budget_remaining": budget_remaining,
            "evidence_root": evidence_root,
        }
        frozen = json.loads(json.dumps(payload))
        sha = MissionCheckpoint.compute_sha256(frozen)

        checkpoint = MissionCheckpoint(
            checkpoint_id=cid,
            mission_id=mission_id,
            checkpoint_type=checkpoint_type,
            timestamp=now,
            mission_state=mission_state,
            objective_state=frozen["objective_state"],
            plan_dag=frozen["plan_dag"],
            agent_states=frozen["agent_states"],
            claims=frozen["claims"],
            workspace_states=frozen["workspace_states"],
            transaction_states=frozen["transaction_states"],
            architecture_hash=architecture_hash,
            contract_hash=contract_hash,
            behavior_hash=behavior_hash,
            verification_ledger=frozen["verification_ledger"],
            budget_remaining=frozen["budget_remaining"],
            evidence_root=evidence_root,
            sha256_hash=sha,
        )

        self._checkpoints[cid] = checkpoint
        self._checkpoint_chain.append(cid)
        return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> Optional[MissionCheckpoint]:
        cp = self._checkpoints.get(checkpoint_id)
        if cp:
            # Validate immutability
            self.validate_integrity(cp)
        return cp

    def get_latest_checkpoint(self) -> Optional[MissionCheckpoint]:
        if not self._checkpoint_chain:
            return None
        return self.get_checkpoint(self._checkpoint_chain[-1])

    def validate_integrity(self, checkpoint: MissionCheckpoint) -> bool:
        """Verifies SHA-256 hash match against state contents."""
        payload = {
            "checkpoint_id": checkpoint.checkpoint_id,
            "mission_id": checkpoint.mission_id,
            "checkpoint_type": checkpoint.checkpoint_type.value,
            "timestamp": checkpoint.timestamp,
            "mission_state": checkpoint.mission_state,
            "objective_state": checkpoint.objective_state,
            "plan_dag": checkpoint.plan_dag,
            "agent_states": checkpoint.agent_states,
            "claims": checkpoint.claims,
            "workspace_states": checkpoint.workspace_states,
            "transaction_states": checkpoint.transaction_states,
            "architecture_hash": checkpoint.architecture_hash,
            "contract_hash": checkpoint.contract_hash,
            "behavior_hash": checkpoint.behavior_hash,
            "verification_ledger": checkpoint.verification_ledger,
            "budget_remaining": checkpoint.budget_remaining,
            "evidence_root": checkpoint.evidence_root,
        }
        expected_sha = MissionCheckpoint.compute_sha256(payload)
        if expected_sha != checkpoint.sha256_hash:
            raise CheckpointTamperError(
                f"Checkpoint {checkpoint.checkpoint_id} has been tampered! "
                f"Expected {expected_sha}, found {checkpoint.sha256_hash}"
            )
        return True

    def list_checkpoints(self) -> List[MissionCheckpoint]:
        return [self._checkpoints[cid] for cid in self._checkpoint_chain]
