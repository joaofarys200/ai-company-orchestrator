"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: bridge.py
MultiAgentCoordinationBridge: Master orchestrator integrating intents, claims, dependencies,
conflict detection, scheduling, arbitration, workspace isolation, 3-way merge, rebase,
deadlock/starvation detection, and shared verification.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .arbiter import ConflictArbiter
from .architecture import ArchitectureCoordinationValidator
from .behavior import BehaviorCoordinationValidator
from .branching import BranchManager
from .cache import CoordinationCache
from .claims import ClaimManager
from .conflicts import AgentConflictDetector
from .contracts import ContractCoordinationValidator
from .convergence import ConvergenceGovernor
from .dependencies import CoordinationDependencyAnalyzer
from .index import CoordinationIndex
from .intent import IntentManager
from .merge import CoordinationMergeEngine
from .metrics import CoordinationMetricsCollector
from .models import (
    AgentChangeSet,
    AgentConflict,
    AgentEngineeringIntent,
    ArbitrationDecision,
    ArbitrationResolution,
    ClaimType,
    ConflictType,
    DeadlockState,
    IntentState,
    MergeResult,
    RebaseResult,
    ResourceClaim,
    ResourceGranularity,
    SchedulingDecision,
)
from .persistence import CoordinationPersistenceStore
from .policy import CoordinationPolicyEngine
from .priority import AgentPriorityModel
from .provenance import ProvenanceGraphTracker
from .rebase import RebaseEngine
from .resources import ResourceManager
from .scheduler import CoordinationScheduler
from .security import SecuritySentinel
from .validator import CoordinationGateValidator
from .verification import SharedVerificationManager
from .workspace import WorkspaceIsolationManager


class MultiAgentCoordinationBridge:
    """Singleton bridge orchestrating the multi-agent engineering coordination pipeline."""

    _instance: Optional[MultiAgentCoordinationBridge] = None

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        db_path: str = ":memory:",
        policy_name: str = "STANDARD",
    ):
        self.workspace_root = workspace_root or os.getcwd()
        self.db_path = db_path

        # Core subsystems
        self.intent_mgr = IntentManager()
        self.claim_mgr = ClaimManager()
        self.resource_mgr = ResourceManager(self.workspace_root)
        self.dependency_analyzer = CoordinationDependencyAnalyzer()
        self.conflict_detector = AgentConflictDetector()
        self.scheduler = CoordinationScheduler(self.claim_mgr)
        self.arbiter = ConflictArbiter()
        self.priority_model = AgentPriorityModel()
        self.workspace_mgr = WorkspaceIsolationManager(self.workspace_root)
        self.branch_mgr = BranchManager()
        self.merge_engine = CoordinationMergeEngine()
        self.rebase_engine = RebaseEngine()
        self.verification_mgr = SharedVerificationManager()
        self.contract_val = ContractCoordinationValidator()
        self.behavior_val = BehaviorCoordinationValidator()
        self.architecture_val = ArchitectureCoordinationValidator()
        self.provenance_tracker = ProvenanceGraphTracker()
        self.security_sentinel = SecuritySentinel()
        self.policy_engine = CoordinationPolicyEngine(policy_name)
        self.convergence_gov = ConvergenceGovernor()
        self.metrics = CoordinationMetricsCollector()
        self.cache = CoordinationCache()
        self.persistence = CoordinationPersistenceStore(self.db_path)
        self.validator = CoordinationGateValidator()
        self.index = CoordinationIndex()

    @classmethod
    def get_instance(
        cls,
        workspace_root: Optional[str] = None,
        db_path: str = ":memory:",
        policy_name: str = "STANDARD",
    ) -> MultiAgentCoordinationBridge:
        if cls._instance is None:
            cls._instance = cls(workspace_root, db_path, policy_name)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def coordinate_intents(
        self,
        intents: List[AgentEngineeringIntent],
    ) -> Dict[str, Any]:
        """Execute the complete coordination and arbitration pipeline across candidate intents."""
        t_start = time.time()
        logs: List[str] = []

        # 1. Register & Validate all intents
        for it in intents:
            ok, msg = self.intent_mgr.register_intent(it)
            logs.append(msg)
            if ok:
                self.intent_mgr.validate_intent(it.intent_id)
                self.metrics.record_intent()
                self.index.index_intent(it.agent_id, it.intent_id, it.requested_files)
                self.persistence.save_intent(it)

        # 2. Security validation
        for it in intents:
            for f in it.requested_files:
                sec_ok, sec_msg = self.security_sentinel.validate_file_safety(f)
                if not sec_ok:
                    logs.append(sec_msg)
                    return {
                        "success": False,
                        "status": "SECURITY_BLOCKED",
                        "reason": sec_msg,
                        "logs": logs,
                    }

        # 3. Detect multi-granularity conflicts
        conflicts = self.conflict_detector.detect_conflicts(intents)
        self.metrics.record_conflict(len(conflicts))
        for c in conflicts:
            self.persistence.save_conflict(c)
        logs.append(f"CONFLICT_DETECTION: Found {len(conflicts)} potential conflicts.")

        # 4. Arbitrate conflicts
        arbitrations: List[ArbitrationDecision] = []
        intent_map = {it.intent_id: it for it in intents}
        for conf in conflicts:
            it_a = intent_map.get(conf.intent_a)
            it_b = intent_map.get(conf.intent_b)
            if it_a and it_b:
                dec = self.arbiter.arbitrate_conflict(conf, it_a, it_b)
                arbitrations.append(dec)
                self.metrics.record_arbitration()
                self.persistence.save_arbitration(dec)
                logs.append(f"ARBITRATED: {conf.conflict_id} -> {dec.resolution.value}")

        # 5. Compute schedule (parallel waves vs serial queue)
        schedule = self.scheduler.schedule_intents(intents)
        is_parallel = schedule.get("decision") == SchedulingDecision.PARALLEL_SAFE.value
        self.metrics.record_wave(is_parallel)
        logs.append(f"SCHEDULE_COMPUTED: {schedule.get('decision')} across {len(schedule.get('parallel_waves', []))} waves.")

        # 6. Check convergence
        conv_state, conv_msg = self.convergence_gov.record_wave(len(conflicts))
        logs.append(f"CONVERGENCE: {conv_state.value} - {conv_msg}")

        elapsed_ms = round((time.time() - t_start) * 1000.0, 2)
        return {
            "success": True,
            "status": schedule.get("decision"),
            "intents_count": len(intents),
            "conflicts": [c.to_dict() for c in conflicts],
            "arbitrations": [a.to_dict() for a in arbitrations],
            "schedule": schedule,
            "convergence_state": conv_state.value,
            "logs": logs,
            "duration_ms": elapsed_ms,
        }

    def detect_deadlocks(self, intents: List[AgentEngineeringIntent]) -> Dict[str, Any]:
        """Detect circular wait conditions in dependency graph."""
        dep_info = self.dependency_analyzer.build_dependency_graph(intents)
        if dep_info["has_cycle"]:
            self.metrics.record_deadlock()
            return {
                "state": DeadlockState.DEADLOCK.value,
                "has_deadlock": True,
                "cycle_nodes": dep_info["cycle_nodes"],
                "resolution": "RESOLVING via intent decomposition or task cancellation",
            }
        return {
            "state": DeadlockState.NO_DEADLOCK.value,
            "has_deadlock": False,
            "cycle_nodes": [],
            "resolution": "NONE",
        }

    def detect_starvation(
        self,
        intents: List[AgentEngineeringIntent],
        max_wait_count: int = 4,
    ) -> Dict[str, Any]:
        """Detect starvation and apply anti-starvation boost."""
        starved = [it for it in intents if it.wait_count >= max_wait_count]
        if starved:
            for it in starved:
                self.metrics.record_starvation_boost()
            # Fair re-ordering
            boosted_order = self.priority_model.order_intents_fairly(intents)
            return {
                "starvation_detected": True,
                "starved_intents": [it.intent_id for it in starved],
                "boosted_order": [it.intent_id for it in boosted_order],
                "action": "PRIORITY_BOOST_APPLIED",
            }
        return {
            "starvation_detected": False,
            "starved_intents": [],
            "boosted_order": [it.intent_id for it in intents],
            "action": "NONE",
        }

    def merge_and_verify(
        self,
        base_contents: Dict[str, str],
        changeset_a: AgentChangeSet,
        changeset_b: AgentChangeSet,
        affected_tests: List[str],
    ) -> Dict[str, Any]:
        """Execute 3-way merge and run shared post-merge verification."""
        merge_res = self.merge_engine.merge_changesets(base_contents, changeset_a, changeset_b)
        self.metrics.record_merge()
        self.persistence.save_merge(merge_res)

        if not merge_res.success:
            return {
                "success": False,
                "status": "MERGE_CONFLICT",
                "merge": merge_res.to_dict(),
                "shared_verification": None,
                "commit_eligibility": None,
            }

        # Shared verification
        all_files = list(set(changeset_a.affected_files).union(set(changeset_b.affected_files)))
        shared_verif = self.verification_mgr.run_shared_verification(
            changesets=[changeset_a, changeset_b],
            all_affected_files=all_files,
            all_affected_tests=affected_tests,
        )

        # Record provenance
        prov_a = self.provenance_tracker.record_coordination_event(
            agent_id=changeset_a.agent_id,
            mission_id="m_coord",
            intent_id=changeset_a.intent_id,
            claim_ids=[],
            transaction_id=changeset_a.transaction_id,
            base_snapshot=changeset_a.base_snapshot,
            patch_hash=changeset_a.compute_patch_hash(),
            merge_hash=merge_res.evidence_hash,
            verification_hash=shared_verif.get("evidence_hash", ""),
        )
        self.persistence.save_provenance(prov_a)

        # Evaluate commit gate
        gate = self.validator.evaluate_commit_eligibility(
            intents_count=2,
            conflicts_count=0,
            arbitrations_count=0,
            merge_results=[merge_res],
            shared_verification_passed=shared_verif["success"],
            security_passed=True,
            provenance_verified=True,
        )

        return {
            "success": shared_verif["success"] and gate["is_eligible"],
            "status": "COMMITTED" if (shared_verif["success"] and gate["is_eligible"]) else "VERIFICATION_FAILED",
            "merge": merge_res.to_dict(),
            "shared_verification": shared_verif,
            "commit_eligibility": gate,
        }

    def get_coordination_status(self) -> Dict[str, Any]:
        """Return runtime coordination status across registered subsystems."""
        return {
            "active_intents": len(self.intent_mgr.intents),
            "active_claims": len(self.claim_mgr.active_claims),
            "active_workspaces": len(self.workspace_mgr.workspaces),
            "convergence_state": self.convergence_gov.state.value,
            "metrics": self.metrics.to_dict(),
            "cache_stats": self.cache.stats(),
        }
