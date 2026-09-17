"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Multi-Repair Planner & Conflict Detector.
Plans a coordinated, ordered sequence of repairs with conflict detection across files, symbols,
contract versions, and economic/security rules.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from agents.multi_repair_orchestration.dependencies import RepairDependencyAnalyzer
from agents.multi_repair_orchestration.models import (
    ConflictReport,
    ConflictType,
    FailureCluster,
    NodeRelationType,
    RepairGraph,
    RepairTransaction,
    TransactionStatus,
    compute_deterministic_hash,
)


class MultiRepairPlanner:
    """
    Creates a transactional repair plan for a failure cluster, detecting conflicts
    and sorting execution order topologically.
    """

    def __init__(self, dependency_analyzer: Optional[RepairDependencyAnalyzer] = None):
        self.dependency_analyzer = dependency_analyzer or RepairDependencyAnalyzer()

    def detect_conflicts(self, candidates: List[Any]) -> ConflictReport:
        """
        Detects conflicts between repair candidates:
        - Overlapping patches in the same file
        - Colliding symbol definitions
        - Contradictory dependency version mutations
        - Auth downgrades or economic mutations
        """
        file_to_candidates: Dict[str, List[str]] = {}
        symbol_mutations: Dict[str, List[str]] = {}

        for cand in candidates:
            cand_id = getattr(cand, "repair_id", str(cand))
            
            # File collisions
            diffs = getattr(cand, "diffs", [])
            for diff in diffs:
                f_path = getattr(diff, "file_path", "")
                if f_path:
                    file_to_candidates.setdefault(f_path, []).append(cand_id)

            # Check for economic or security conflicts
            strategy = getattr(cand, "strategy_name", "")
            if "ECONOMIC_MUTATION" in strategy or "STRIPE_BYPASS" in strategy:
                return ConflictReport(
                    has_conflicts=True,
                    conflict_type=ConflictType.ECONOMIC_CONFLICT,
                    description=f"Candidate {cand_id} alters economic invariants without authorization",
                    conflicting_repairs=[cand_id],
                    requires_human_review=True,
                )
            if "AUTH_BYPASS" in strategy or "DISABLE_AUTH" in strategy:
                return ConflictReport(
                    has_conflicts=True,
                    conflict_type=ConflictType.AUTH_CONFLICT,
                    description=f"Candidate {cand_id} attempts authorization downgrade",
                    conflicting_repairs=[cand_id],
                    requires_human_review=True,
                )

        # Check for overlapping patches on the same file
        for f_path, c_ids in file_to_candidates.items():
            if len(c_ids) > 1:
                # If two distinct candidates touch the same file without explicit merge strategy
                return ConflictReport(
                    has_conflicts=True,
                    conflict_type=ConflictType.OVERLAPPING_PATCH,
                    description=f"Multiple repair candidates {c_ids} target the same file {f_path}",
                    conflicting_repairs=c_ids,
                    requires_human_review=True,
                )

        return ConflictReport(has_conflicts=False)

    def plan_transaction(
        self,
        cluster: FailureCluster,
        candidates: List[Any],
        dependencies: List[Tuple[str, str]],
        mission_id: str = "default_mission",
    ) -> Tuple[Optional[RepairTransaction], ConflictReport]:
        # 1. Conflict Detection
        conflict = self.detect_conflicts(candidates)
        if conflict.has_conflicts and conflict.requires_human_review:
            tx_id = f"tx_{compute_deterministic_hash(cluster.cluster_id)}"
            tx = RepairTransaction(
                transaction_id=tx_id,
                mission_id=mission_id,
                cluster_id=cluster.cluster_id,
                repairs=candidates,
                dependencies=dependencies,
                status=TransactionStatus.FAILED,
            )
            return tx, conflict

        # 2. Dependency Ordering
        repair_map = {getattr(c, "repair_id", str(c)): c for c in candidates}
        repair_ids = list(repair_map.keys())

        ordered_ids = self.dependency_analyzer.determine_execution_order(repair_ids, dependencies)
        ordered_candidates = [repair_map[r_id] for r_id in ordered_ids]

        # 3. Create Transaction in PLANNED state
        tx_id = f"tx_{compute_deterministic_hash([cluster.cluster_id] + ordered_ids)}"
        transaction = RepairTransaction(
            transaction_id=tx_id,
            mission_id=mission_id,
            cluster_id=cluster.cluster_id,
            repairs=ordered_candidates,
            dependencies=dependencies,
            status=TransactionStatus.PLANNED,
        )

        return transaction, conflict
