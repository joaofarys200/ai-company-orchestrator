"""
JARVIS OS — Phase 44: Semantic Graph System Bridge
Connects the Cross-Language Semantic Graph to Predictive Impact (Phase 39),
Task Reconciliation (Phase 39.2), Autonomous Loop (Phase 40),
Decision Calibration (Phase 41), and Experience Memory (Phases 42/43).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

from agents.semantic_graph.adapters import SemanticAdapterRegistry
from agents.semantic_graph.contracts import ContractRegistry
from agents.semantic_graph.graph import CrossLanguageSemanticGraph
from agents.semantic_graph.models import (
    ConfidenceClass,
    SemanticNode,
    SemanticNodeType,
    TranslatedTask,
    ValidationStatus,
)


class SemanticGraphBridge:
    """Orchestrates interoperability between the Cross-Language Semantic Graph and core OS sub-systems."""

    def __init__(
        self,
        graph: CrossLanguageSemanticGraph,
        contracts: ContractRegistry,
        adapters: SemanticAdapterRegistry | None = None,
    ) -> None:
        self.graph = graph
        self.contracts = contracts
        self.adapters = adapters or SemanticAdapterRegistry()

    # -------------------------------------------------------------------------
    # 1. Predictive Impact Integration (Phase 39)
    # -------------------------------------------------------------------------
    def propagate_predictive_impact(
        self,
        intent_category: str,
        focal_node_ids: list[str],
    ) -> dict[str, Any]:
        """Calculates multi-ecosystem predicted impact from intent and focal semantic nodes."""
        blast_radius = self.graph.calculate_blast_radius(focal_node_ids)
        affected_nodes = [self.graph.get_node(nid) for nid in blast_radius if self.graph.get_node(nid)]

        # Classify by ecosystem / layer
        frontend_nodes = [n for n in affected_nodes if n.node_type == SemanticNodeType.FRONTEND_COMPONENT]
        api_nodes = [n for n in affected_nodes if n.node_type in (SemanticNodeType.API_CONTRACT, SemanticNodeType.API_ENDPOINT)]
        backend_nodes = [n for n in affected_nodes if n.node_type == SemanticNodeType.BACKEND_SERVICE]
        db_nodes = [n for n in affected_nodes if n.node_type in (SemanticNodeType.PERSISTENCE_OPERATION, SemanticNodeType.DATA_MODEL)]
        test_nodes = [n for n in affected_nodes if n.node_type in (SemanticNodeType.TEST, SemanticNodeType.BROWSER_SCENARIO)]

        # Scope inference
        scope = "LOCAL"
        if len(backend_nodes) > 0 and len(frontend_nodes) > 0:
            scope = "CROSS_MODULE"
        if len(db_nodes) > 0 or len(test_nodes) > 0:
            scope = "ARCHITECTURAL"

        return {
            "intent_category": intent_category,
            "focal_nodes": focal_node_ids,
            "blast_radius_count": len(blast_radius),
            "predicted_scope": scope,
            "ecosystems_involved": list(set(n.ecosystem for n in affected_nodes if n.ecosystem != "agnostic")),
            "frontend_impact": [n.node_id for n in frontend_nodes],
            "api_impact": [n.node_id for n in api_nodes],
            "backend_impact": [n.node_id for n in backend_nodes],
            "persistence_impact": [n.node_id for n in db_nodes],
            "validation_impact": [n.node_id for n in test_nodes],
        }

    # -------------------------------------------------------------------------
    # 2. Task Reconciliation Integration (Phase 39.2)
    # -------------------------------------------------------------------------
    def reconcile_translated_tasks(
        self,
        translated_tasks: list[TranslatedTask],
    ) -> dict[str, Any]:
        """Verifies that translated cross-language tasks satisfy causal traceability and DAG invariants."""
        task_ids = {t.task_id for t in translated_tasks}
        issues: list[str] = []

        # Check dependency resolution
        for t in translated_tasks:
            for dep in t.dependencies:
                if dep not in task_ids:
                    issues.append(f"Task '{t.task_id}' depends on unresolved task ID '{dep}'")

            # Check causal traceability
            if not t.translation_reason or not t.evidence:
                issues.append(f"Task '{t.task_id}' lacks causal justification or evidence references.")

        is_consistent = len(issues) == 0
        return {
            "is_consistent": is_consistent,
            "verdict": "CONSISTENT" if is_consistent else "INCONSISTENT",
            "task_count": len(translated_tasks),
            "issues": issues,
        }

    # -------------------------------------------------------------------------
    # 3. Decision Calibration Integration (Phase 41)
    # -------------------------------------------------------------------------
    def populate_decision_trace_metadata(
        self,
        decision_trace_data: dict[str, Any],
        active_node_ids: list[str],
    ) -> dict[str, Any]:
        """Injects cross-language semantic telemetry into a Phase 41 DecisionTrace."""
        active_nodes = [self.graph.get_node(nid) for nid in active_node_ids if self.graph.get_node(nid)]
        adapters_used = set()
        validation_status = "VALID"

        for node in active_nodes:
            for edge in self.graph.get_out_edges(node.node_id):
                target = self.graph.get_node(edge.target)
                if target:
                    adapter, st, _ = self.adapters.resolve_adapter(node, target, edge.relation_type)
                    if adapter:
                        adapters_used.add(adapter.adapter_id)
                    if st == ValidationStatus.UNCERTAIN:
                        validation_status = "UNCERTAIN"
                    elif st == ValidationStatus.INVALID and validation_status != "UNCERTAIN":
                        validation_status = "INVALID"

        decision_trace_data["semantic_nodes"] = [n.node_id for n in active_nodes]
        decision_trace_data["semantic_edges"] = [e.edge_id for n in active_nodes for e in self.graph.get_out_edges(n.node_id)]
        decision_trace_data["translation_adapters"] = sorted(list(adapters_used))
        decision_trace_data["semantic_validation_status"] = validation_status
        return decision_trace_data

    # -------------------------------------------------------------------------
    # 4. Experience Memory Cross-Language Transfer Check (Phases 42/43)
    # -------------------------------------------------------------------------
    def validate_memory_transfer(
        self,
        source_experience_technology: list[str],
        target_mission_ecosystem: str,
    ) -> tuple[bool, str, ConfidenceClass]:
        """Enforces that experience from one stack (e.g. React + FastAPI) cannot transfer to another (e.g. Vue + Django)
        without formal adapter evidence."""
        source_set = {s.lower() for s in source_experience_technology}
        target_eco = target_mission_ecosystem.lower()

        # Direct stack match
        if target_eco in source_set:
            return True, f"Experience stack matches target ecosystem '{target_eco}'.", ConfidenceClass.DIRECT

        # Check if there is an adapter for this ecosystem combination
        for adapter in self.adapters.list_adapters():
            if adapter.source_ecosystem in source_set and adapter.target_ecosystem == target_eco:
                return True, f"Formal adapter '{adapter.adapter_id}' permits transfer from '{adapter.source_ecosystem}' to '{target_eco}'.", ConfidenceClass.CONTRACTUAL

        # Otherwise: UNCERTAIN
        return False, f"No formal adapter connects experience stack {source_experience_technology} to target '{target_eco}': marked UNCERTAIN.", ConfidenceClass.UNCERTAIN
