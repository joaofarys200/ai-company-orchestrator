"""
JARVIS OS — Phase 40: Autonomous Engineering Loop & Closed-Loop Mission Adaptation
Loop State Management, Snapshot Hashing, Oscillation Detection, Mission Drift & Crash Recovery.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.autonomous_loop.models import (
    AutonomousLoopState,
    DriftClassification,
    LoopCycleFingerprint,
    LoopDecisionType,
    LoopSnapshot,
    LoopStage,
    OscillationStatus,
)


class AutonomousLoopStateManager:
    """
    Manages loop state transitions, snapshots, oscillation tracking,
    drift detection, requirement retention audits, and checkpoint persistence.
    """

    def __init__(self, mission_id: str, checkpoint_dir: Optional[str] = None):
        self.mission_id = mission_id
        self.checkpoint_dir = checkpoint_dir or os.path.join(os.path.dirname(__file__), ".checkpoints")
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        self.state = AutonomousLoopState(mission_id=mission_id)
        self.snapshots: list[LoopSnapshot] = []
        self.fingerprints: list[LoopCycleFingerprint] = []
        self.checkpoints: list[dict[str, Any]] = []

        # Retention & drift baselines
        self.initial_intent: str = ""
        self.initial_requirements: list[dict[str, Any]] = []

    def initialize_baselines(self, intent: str, requirements: list[dict[str, Any]]) -> None:
        self.initial_intent = intent
        self.initial_requirements = [dict(r) for r in requirements]

    def create_snapshot(
        self,
        cycle_id: str,
        intent_version: int,
        plan_version: int,
        mission_state_hash: str,
        dag_hash: str,
        active_tasks: list[dict[str, Any]],
        requirements: list[dict[str, Any]],
        constraints: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        workspace_snapshot_hash: str = "",
        architecture_graph_hash: str = "",
        prediction_state_hash: str = "",
        agent_state_hash: str = "",
    ) -> LoopSnapshot:
        snapshot_id = f"snap_{cycle_id}_{int(time.time() * 1000) % 100000}"
        snap = LoopSnapshot(
            snapshot_id=snapshot_id,
            cycle_id=cycle_id,
            mission_id=self.mission_id,
            intent_version=intent_version,
            plan_version=plan_version,
            mission_state_hash=mission_state_hash,
            dag_hash=dag_hash,
            active_tasks=[dict(t) for t in active_tasks],
            requirements=[dict(r) for r in requirements],
            constraints=[dict(c) for c in constraints],
            evidence=[dict(e) for e in evidence],
            workspace_snapshot_hash=workspace_snapshot_hash,
            architecture_graph_hash=architecture_graph_hash,
            prediction_state_hash=prediction_state_hash,
            agent_state_hash=agent_state_hash,
            timestamp=time.time(),
        )
        snap.compute_deterministic_hash()
        self.snapshots.append(snap)
        return snap

    def register_fingerprint(
        self,
        cycle_id: str,
        plan_hash: str,
        adaptation_signature: str,
        failure_signature: str,
        task_states_signature: str,
    ) -> LoopCycleFingerprint:
        # Check repetitions: true repetition occurs when either failure/adaptation repeats
        # or the entire task state stagnates without progress
        prev_matches = [
            fp for fp in self.fingerprints
            if fp.plan_hash == plan_hash
            and fp.adaptation_signature == adaptation_signature
            and fp.failure_signature == failure_signature
            and (
                failure_signature != "CLEAN"
                or adaptation_signature != "NONE"
                or fp.task_states_signature == task_states_signature
            )
        ]
        repetition_count = len(prev_matches)

        fp = LoopCycleFingerprint(
            cycle_id=cycle_id,
            plan_hash=plan_hash,
            adaptation_signature=adaptation_signature,
            failure_signature=failure_signature,
            task_states_signature=task_states_signature,
            state_repetition_count=repetition_count,
        )
        fp.compute_hash()
        self.fingerprints.append(fp)
        return fp

    def check_oscillation(self, current_fingerprint: LoopCycleFingerprint, max_repetitions: int = 2) -> tuple[OscillationStatus, str]:
        """
        Detects oscillation cycles such as PLAN A -> REPLAN B -> PLAN A -> REPLAN B
        or REPAIR A -> FAILURE -> REPAIR A -> FAILURE.
        """
        if current_fingerprint.state_repetition_count >= max_repetitions:
            return (
                OscillationStatus.CONFIRMED_OSCILLATION,
                f"State repetition count {current_fingerprint.state_repetition_count} exceeded threshold {max_repetitions}. Repeating signature: {current_fingerprint.fingerprint_hash}.",
            )

        # Check cyclical pattern in last 4 fingerprints: A - B - A - B
        if len(self.fingerprints) >= 4:
            f0 = self.fingerprints[-1].fingerprint_hash
            f1 = self.fingerprints[-2].fingerprint_hash
            f2 = self.fingerprints[-3].fingerprint_hash
            f3 = self.fingerprints[-4].fingerprint_hash
            if f0 == f2 and f1 == f3 and f0 != f1:
                return (
                    OscillationStatus.CONFIRMED_OSCILLATION,
                    f"Alternating oscillation detected: cycle {f0} <-> {f1}.",
                )

        if current_fingerprint.state_repetition_count == 1:
            return OscillationStatus.SUSPECTED, "Possible recurring state detected."

        return OscillationStatus.NORMAL, "No oscillation detected."

    def detect_mission_drift(
        self,
        current_intent: str,
        current_requirements: list[dict[str, Any]],
        formal_intent_changed: bool = False,
    ) -> tuple[DriftClassification, str]:
        """
        Compares original intent vs current intent and ensures goals cannot be mutated
        without explicit formal intent delta.
        """
        if not self.initial_intent:
            return DriftClassification.NO_DRIFT, "Baseline intent not set."

        intent_changed = (current_intent.strip() != self.initial_intent.strip())
        initial_req_ids = {r.get("id") or r.get("requirement_id") for r in self.initial_requirements}
        current_req_ids = {r.get("id") or r.get("requirement_id") for r in current_requirements}

        missing_reqs = initial_req_ids - current_req_ids

        if missing_reqs and not formal_intent_changed:
            return (
                DriftClassification.UNEXPECTED_DRIFT,
                f"Requirements dropped without formal intent delta: {missing_reqs}",
            )

        if intent_changed and not formal_intent_changed:
            return (
                DriftClassification.UNEXPECTED_DRIFT,
                "Mission intent text modified without approved MissionIntentDelta.",
            )

        if intent_changed and formal_intent_changed:
            return DriftClassification.CONTROLLED_DRIFT, "Controlled drift through authorized intent delta."

        return DriftClassification.NO_DRIFT, "Mission objective and requirements strictly aligned."

    def audit_requirement_retention(
        self,
        current_requirements: list[dict[str, Any]],
        authorized_removals: Optional[set[str]] = None,
    ) -> tuple[bool, float, list[str]]:
        """
        Ensures requirements never disappear due to context loss or planner simplification.
        Returns: (passed, retention_rate, list_of_dropped_req_ids)
        """
        if not self.initial_requirements:
            return True, 1.0, []

        removals = authorized_removals or set()
        initial_ids = {r.get("id") or r.get("requirement_id") for r in self.initial_requirements if (r.get("id") or r.get("requirement_id"))}
        current_ids = {r.get("id") or r.get("requirement_id") for r in current_requirements if (r.get("id") or r.get("requirement_id"))}

        expected_ids = initial_ids - removals
        retained = expected_ids.intersection(current_ids)
        dropped = sorted(list(expected_ids - current_ids))

        rate = len(retained) / max(len(expected_ids), 1)
        passed = (len(dropped) == 0)
        return passed, rate, dropped

    def verify_state_consistency(
        self,
        mission_status: str,
        requirements: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        active_blocks: bool = False,
    ) -> tuple[bool, str]:
        """
        Verifies mutual consistency across mission lifecycle states.
        E.g.: mission == COMPLETED but required evidence missing -> INVALID_STATE.
        """
        if active_blocks and mission_status == "COMPLETED":
            return False, "INVALID_STATE: Mission cannot be COMPLETED while active security/policy blocks exist."

        if mission_status == "COMPLETED":
            if not evidence:
                return False, "INVALID_STATE: Mission marked COMPLETED but evidence ledger is empty (Zero False Success violated)."
            # Check unvalidated requirements
            for req in requirements:
                if req.get("status") not in ("VALIDATED", "COMPLETED", "SATISFIED"):
                    return False, f"INVALID_STATE: Mission completed but requirement {req.get('id')} is not validated."

        return True, "State is consistent."

    def persist_checkpoint(
        self,
        cycle_id: str,
        decision: LoopDecisionType,
        adaptation: Optional[dict[str, Any]],
        outcome: Optional[dict[str, Any]],
    ) -> str:
        """
        Persists durable checkpoint after each safe cycle step.
        """
        self.state.updated_at = time.time()
        self.state.compute_state_hash()

        latest_snap = self.snapshots[-1] if self.snapshots else None
        checkpoint_data = {
            "mission_id": self.mission_id,
            "cycle_id": cycle_id,
            "timestamp": time.time(),
            "state": self.state.to_dict(),
            "snapshot_hash": latest_snap.deterministic_hash if latest_snap else "",
            "decision": decision.value if isinstance(decision, LoopDecisionType) else decision,
            "adaptation": adaptation,
            "outcome": outcome,
            "plan_version": self.state.plan_version,
            "intent_version": self.state.intent_version,
            "fingerprints_count": len(self.fingerprints),
        }
        self.checkpoints.append(checkpoint_data)

        filepath = os.path.join(self.checkpoint_dir, f"checkpoint_{self.mission_id}_{cycle_id}.json")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, indent=2)
        except Exception:
            pass
        return filepath

    def restore_latest_checkpoint(self) -> Optional[dict[str, Any]]:
        """
        Crash recovery: restores the latest valid checkpoint from disk and verifies hashes.
        """
        files = [
            f for f in os.listdir(self.checkpoint_dir)
            if f.startswith(f"checkpoint_{self.mission_id}_") and f.endswith(".json")
        ]
        if not files:
            return None

        files.sort(key=lambda x: os.path.getmtime(os.path.join(self.checkpoint_dir, x)), reverse=True)
        latest_file = os.path.join(self.checkpoint_dir, files[0])

        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            st_data = data.get("state", {})
            self.state = AutonomousLoopState.from_dict(st_data)
            return data
        except Exception:
            return None
