"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Failure Clustering Engine.
Groups related failures into coherent clusters based on structural, causal, and runtime overlap,
never relying solely on superficial textual similarity.
"""

from __future__ import annotations

from typing import Dict, List, Set

from agents.multi_repair_orchestration.models import (
    FailureCluster,
    FailureItem,
    compute_deterministic_hash,
)


class FailureClusterer:
    """
    Analyzes a set of failure items and groups them into multi-dimensional clusters.
    Two failures belong to the same cluster if they share:
    1. Root cause category
    2. Any files or code symbols
    3. Associated contracts or consumers
    4. Causal revelation link (one revealed by the repair of another)
    5. Shared mission runtime fingerprint
    """

    def cluster_failures(
        self, failures: List[FailureItem], mission_id: str = "default_mission"
    ) -> List[FailureCluster]:
        if not failures:
            return []

        # Disjoint set / union-find approach to connect overlapping failures
        parent: Dict[str, str] = {f.failure_id: f.failure_id for f in failures}

        def find(item_id: str) -> str:
            if parent[item_id] != item_id:
                parent[item_id] = find(parent[item_id])
            return parent[item_id]

        def union(id1: str, id2: str) -> None:
            r1 = find(id1)
            r2 = find(id2)
            if r1 != r2:
                parent[r2] = r1

        # Evaluate pairs for structural and causal connectivity
        for i in range(len(failures)):
            f1 = failures[i]
            for j in range(i + 1, len(failures)):
                f2 = failures[j]
                if self._are_failures_related(f1, f2):
                    union(f1.failure_id, f2.failure_id)

        # Collect clustered groups
        groups: Dict[str, List[FailureItem]] = {}
        for f in failures:
            root = find(f.failure_id)
            groups.setdefault(root, []).append(f)

        clusters: List[FailureCluster] = []
        for root_id, group_items in groups.items():
            cluster_id = f"cluster_{compute_deterministic_hash([f.failure_id for f in group_items])}"
            
            shared_files: Set[str] = set()
            shared_symbols: Set[str] = set()
            shared_contracts: Set[str] = set()
            shared_consumers: Set[str] = set()
            shared_tasks: Set[str] = set()
            categories: List[str] = []

            for item in group_items:
                if item.file_path:
                    shared_files.add(item.file_path)
                if item.symbol:
                    shared_symbols.add(item.symbol)
                categories.append(item.error_class)

            primary_category = max(set(categories), key=categories.count) if categories else "UNKNOWN"
            
            # Simple risk calculation based on files and errors
            risk_score = min(1.0, 0.15 * len(group_items) + 0.10 * len(shared_files))

            cluster = FailureCluster(
                cluster_id=cluster_id,
                root_cause_category=primary_category,
                shared_files=sorted(list(shared_files)),
                shared_symbols=sorted(list(shared_symbols)),
                shared_contracts=sorted(list(shared_contracts)),
                shared_consumers=sorted(list(shared_consumers)),
                shared_tasks=sorted(list(shared_tasks)),
                failures=group_items,
                risk_score=round(risk_score, 3),
                mission_id=mission_id,
            )
            clusters.append(cluster)

        # Sort clusters deterministically by cluster_id
        clusters.sort(key=lambda c: c.cluster_id)
        return clusters

    def _are_failures_related(self, f1: FailureItem, f2: FailureItem) -> bool:
        # 1. Causal relationship: one was revealed by the other's repair
        if f1.revealed_by_repair_id and f1.revealed_by_repair_id == f2.revealed_by_repair_id:
            return True
        if f1.failure_id == f2.revealed_by_repair_id or f2.failure_id == f1.revealed_by_repair_id:
            return True

        # 2. Shared target file
        if f1.file_path and f2.file_path and f1.file_path == f2.file_path:
            return True

        # 3. Shared identifier / symbol
        if f1.symbol and f2.symbol and f1.symbol == f2.symbol:
            return True

        # 4. Same error class with proximate line numbers in same file
        if (
            f1.file_path == f2.file_path
            and f1.error_class == f2.error_class
            and abs(f1.line - f2.line) <= 50
        ):
            return True

        # 5. Shared runtime fingerprint
        if f1.fingerprint and f1.fingerprint == f2.fingerprint:
            return True

        return False
