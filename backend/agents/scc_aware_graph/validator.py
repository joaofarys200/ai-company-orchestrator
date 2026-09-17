from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from .models import CondensationDAG, StronglyConnectedComponent


class SCCAwareValidator:
    """Performs formal mathematical validation of SCC completeness and DAG acyclicity."""

    @classmethod
    def validate_partition_completeness(
        cls,
        raw_nodes: List[str],
        sccs: List[StronglyConnectedComponent],
    ) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        raw_set = set(raw_nodes)

        covered_nodes: Set[str] = set()
        for scc in sccs:
            for node in scc.nodes:
                if node in covered_nodes:
                    errors.append(f"Node {node} appears in multiple SCCs")
                covered_nodes.add(node)

        missing = raw_set - covered_nodes
        if missing:
            errors.append(f"Missing {len(missing)} nodes from SCC partition: {list(missing)[:5]}")

        total_scc_size = sum(s.size for s in sccs)
        if total_scc_size != len(raw_nodes):
            errors.append(f"Sum of SCC sizes ({total_scc_size}) does not match raw node count ({len(raw_nodes)})")

        return (len(errors) == 0), errors

    @classmethod
    def validate_acyclicity(cls, dag: CondensationDAG) -> Tuple[bool, str]:
        if not dag.is_acyclic:
            return False, "DAG Kahn validation failed: cyclic meta-edge found"
        if len(dag.topological_ordering) != len(dag.nodes):
            return False, f"Topological order length ({len(dag.topological_ordering)}) != DAG node count ({len(dag.nodes)})"
        return True, "DAG is strictly acyclic"

    @classmethod
    def validate_dag(cls, dag: CondensationDAG) -> Tuple[bool, str]:
        return cls.validate_acyclicity(dag)


    @classmethod
    def validate_determinism(cls, run_a: List[List[str]], run_b: List[List[str]]) -> bool:
        if len(run_a) != len(run_b):
            return False
        for comp_a, comp_b in zip(run_a, run_b):
            if comp_a != comp_b:
                return False
        return True
