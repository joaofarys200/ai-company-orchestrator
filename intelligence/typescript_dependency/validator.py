"""
JARVIS OS — Phase 39.1: TypeScript Graph Validator
Validates structural integrity, invariant compliance, absence of duplicate nodes/edges,
and canonical path consistency for the Normalized TypeScript Graph.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set, Tuple

from intelligence.typescript_dependency.graph import NormalizedTypeScriptGraph


class TypeScriptGraphValidator:
    """
    Ensures mathematical soundness and invariant compliance for the TypeScript dependency graph.
    """

    @classmethod
    def validate_graph(
        cls,
        graph: NormalizedTypeScriptGraph,
        workspace_root: str,
    ) -> Dict[str, Any]:
        """
        Runs comprehensive integrity checks on the graph:
        1. No duplicate nodes.
        2. No duplicate edges.
        3. No self-edges unless semantically recursive.
        4. Resolved targets exist either in graph nodes or physically on disk.
        5. Forward and reverse adjacency symmetry.
        6. Path normalization consistency.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Check Node Normalization
        seen_nodes: Set[str] = set()
        for node in graph.nodes:
            if "\\" in node:
                errors.append(f"Node '{node}' contains un-normalized backslashes.")
            if node in seen_nodes:
                errors.append(f"Duplicate node detected: '{node}'.")
            seen_nodes.add(node)

        # 2. Check Edge Uniqueness and Targets
        seen_edges: Set[Tuple[str, str, str, Optional[str]]] = set()
        for edge in graph.edges:
            edge_key = (edge.source, edge.target, edge.relation_type.value, edge.symbol)
            if edge_key in seen_edges:
                errors.append(f"Duplicate edge detected: {edge.source} -> {edge.target} ({edge.relation_type.value}).")
            seen_edges.add(edge_key)

            # Self-edge check
            if edge.source == edge.target:
                warnings.append(f"Self-referencing edge found: {edge.source} imports or references itself.")

            # Target existence check
            if edge.resolved:
                if edge.target not in graph.nodes:
                    abs_target = os.path.join(workspace_root, edge.target)
                    if not os.path.exists(abs_target):
                        errors.append(
                            f"Resolved target does not exist physically or in graph: '{edge.target}' referenced by '{edge.source}'."
                        )

        # 3. Check Forward and Reverse Edge Adjacency Consistency
        for src, targets in graph.forward_edges.items():
            for tgt in targets:
                if src not in graph.reverse_edges.get(tgt, set()):
                    errors.append(f"Adjacency asymmetry: {src} -> {tgt} exists in forward_edges but missing in reverse_edges.")

        for tgt, sources in graph.reverse_edges.items():
            for src in sources:
                if tgt not in graph.forward_edges.get(src, set()):
                    errors.append(f"Adjacency asymmetry: {tgt} <- {src} exists in reverse_edges but missing in forward_edges.")

        return {
            "is_valid": len(errors) == 0,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
            "total_nodes_validated": len(graph.nodes),
            "total_edges_validated": len(graph.edges),
        }
