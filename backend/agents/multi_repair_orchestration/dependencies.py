"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Repair Dependency Analyzer.
Performs topological dependency analysis (Kahn's algorithm), enforcing producer-before-consumer
ordering with deterministic tie-breaking.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from agents.multi_repair_orchestration.models import (
    NodeRelationType,
    RepairGraph,
)


class DependencyCycleError(Exception):
    pass


class RepairDependencyAnalyzer:
    """
    Computes deterministic execution order for repair actions using topological sorting.
    Enforces producer repairs before consumer repairs.
    """

    def determine_execution_order(
        self,
        repair_ids: List[str],
        dependencies: List[Tuple[str, str]],  # (producer_id, consumer_id) -> consumer depends on producer
        repairs_meta: Dict[str, Dict[str, Any]] | None = None,
    ) -> List[str]:
        """
        Sorts repair_ids such that if (P, C) is in dependencies, P appears before C.
        Ties are broken lexicographically by repair_id for complete determinism.
        """
        repairs_meta = repairs_meta or {}
        in_degree: Dict[str, int] = {r: 0 for r in repair_ids}
        adj: Dict[str, List[str]] = {r: [] for r in repair_ids}

        # Validate explicit dependencies
        for prod, cons in dependencies:
            if prod in in_degree and cons in in_degree:
                adj[prod].append(cons)
                in_degree[cons] += 1

        # Implicit producer-before-consumer checks if metadata provided
        for r1 in repair_ids:
            meta1 = repairs_meta.get(r1, {})
            type1 = meta1.get("type", "").lower()
            for r2 in repair_ids:
                if r1 == r2:
                    continue
                meta2 = repairs_meta.get(r2, {})
                type2 = meta2.get("type", "").lower()
                # If r1 is backend/producer and r2 is frontend/consumer and they share contracts/symbols
                if "backend" in type1 and "consumer" in type2:
                    shared = set(meta1.get("symbols", [])).intersection(set(meta2.get("symbols", [])))
                    if shared and r2 not in adj[r1]:
                        adj[r1].append(r2)
                        in_degree[r2] += 1

        # Kahn's Algorithm with deterministic priority queue / sorted list
        zero_in_degree = [r for r in repair_ids if in_degree[r] == 0]
        zero_in_degree.sort()  # Lexicographical tie-breaking

        ordered: List[str] = []
        while zero_in_degree:
            curr = zero_in_degree.pop(0)
            ordered.append(curr)

            for neighbor in adj.get(curr, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    zero_in_degree.append(neighbor)
                    zero_in_degree.sort()

        if len(ordered) != len(repair_ids):
            remaining = [r for r in repair_ids if r not in ordered]
            raise DependencyCycleError(
                f"Cyclic dependency detected in repair orchestration among candidates: {remaining}"
            )

        return ordered
