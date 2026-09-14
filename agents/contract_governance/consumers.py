"""
JARVIS OS — Phase 46: Contract Consumer Registry & Semantic Impact Analyzer
Reverse index linking ApiSemanticContracts to downstream consumers across
Frontend, Backend, Persistence, Tests, Browser QA, and Semantic Graph Nodes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from agents.contract_governance.models import (
    ConsumerImpact,
    ConsumerImpactLevel,
)
from agents.semantic_graph.models import SemanticNodeType, SemanticRelationType


class ContractConsumerRegistry:
    """Maintains a fast reverse-index from contracts to all dependent components."""

    def __init__(self) -> None:
        self._registry: Dict[str, List[ConsumerImpact]] = {}

    def register_consumer(self, contract_id: str, consumer: ConsumerImpact) -> None:
        """Registers a known consumer for a given contract ID."""
        if contract_id not in self._registry:
            self._registry[contract_id] = []
        # Prevent duplicates
        for existing in self._registry[contract_id]:
            if existing.consumer_id == consumer.consumer_id and existing.consumer_type == consumer.consumer_type:
                return
        self._registry[contract_id].append(consumer)

    def get_consumers(self, contract_id: str) -> List[ConsumerImpact]:
        """Returns all registered consumers for a contract ID."""
        return list(self._registry.get(contract_id, []))

    def clear(self) -> None:
        self._registry.clear()

    def discover_consumers_from_graph(
        self,
        graph: Any,
        contract_id: str,
        contract_node_id: Optional[str] = None,
    ) -> List[ConsumerImpact]:
        """Traverses the CrossLanguageSemanticGraph to locate all downstream consumers of a contract.
        
        Traces:
        CONTRACT -> API consumer (FRONTEND)
        CONTRACT -> BACKEND_SERVICE (SERVES)
        CONTRACT -> TEST (TESTS)
        CONTRACT -> BROWSER_SCENARIO (VALIDATES)
        """
        discovered: List[ConsumerImpact] = []
        seen_nodes: Set[str] = set()

        # Check registered direct consumers first
        for registered in self.get_consumers(contract_id):
            discovered.append(registered)
            seen_nodes.add(registered.consumer_id)

        if not graph or not hasattr(graph, "get_node"):
            return discovered

        target_node_id = contract_node_id or f"api_{contract_id}"
        if not graph.get_node(target_node_id):
            # Try searching all nodes
            for nid, node in getattr(graph, "_nodes", {}).items():
                if node.type == SemanticNodeType.API_CONTRACT and (contract_id in nid or node.metadata.get("contract_id") == contract_id):
                    target_node_id = nid
                    break

        if not graph.get_node(target_node_id):
            return discovered

        # Direct edges connected to the contract (who consumes/tests/calls this contract)
        all_edges = []
        if hasattr(graph, "get_edges_for_node"):
            all_edges = graph.get_edges_for_node(target_node_id)
        elif hasattr(graph, "get_in_edges") and hasattr(graph, "get_out_edges"):
            all_edges = graph.get_in_edges(target_node_id) + graph.get_out_edges(target_node_id)
        elif hasattr(graph, "edges"):
            all_edges = [
                e for e in graph.edges.values()
                if getattr(e, "source", "") == target_node_id or getattr(e, "target", "") == target_node_id
                or getattr(e, "source_id", "") == target_node_id or getattr(e, "target_id", "") == target_node_id
            ]

        for edge in all_edges:
            src = getattr(edge, "source", None) or getattr(edge, "source_id", "")
            tgt = getattr(edge, "target", None) or getattr(edge, "target_id", "")
            other_id = src if tgt == target_node_id else tgt
            if not other_id or other_id in seen_nodes:
                continue
            seen_nodes.add(other_id)

            node = graph.get_node(other_id)
            if not node:
                continue

            # Determine consumer type and impact level
            impact_level = ConsumerImpactLevel.DIRECT
            rel = getattr(edge, "relation_type", None) or getattr(edge, "relation", "CONNECTED_TO")
            rel_name = rel.value if hasattr(rel, "value") else str(rel)

            if node.type == SemanticNodeType.FRONTEND_COMPONENT:
                c_type = "FRONTEND_COMPONENT"
                desc = f"Frontend component '{node.name}' directly consumes endpoint via {rel_name}"
            elif node.type == SemanticNodeType.BACKEND_SERVICE:
                c_type = "BACKEND_SERVICE"
                desc = f"Backend service '{node.name}' implements/serves endpoint via {rel_name}"
            elif node.type == SemanticNodeType.TEST:
                c_type = "TEST"
                desc = f"Automated test suite '{node.name}' tests endpoint contract"
            elif node.type == SemanticNodeType.BROWSER_SCENARIO:
                c_type = "BROWSER_SCENARIO"
                desc = f"Browser QA scenario '{node.name}' validates user flow consuming contract"
            elif node.type == SemanticNodeType.TASK:
                c_type = "TASK"
                desc = f"Task '{node.name}' depends on contract implementation"
            else:
                c_type = "SEMANTIC_GRAPH_NODE"
                impact_level = ConsumerImpactLevel.INDIRECT
                desc = f"Graph entity '{node.name}' ({node.type.value if hasattr(node.type, 'value') else node.type}) linked to contract"

            discovered.append(
                ConsumerImpact(
                    consumer_id=node.node_id,
                    consumer_type=c_type,
                    impact_level=impact_level,
                    description=desc,
                )
            )

        return discovered
