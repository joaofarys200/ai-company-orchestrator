"""
JARVIS OS — Phase 47: Polymorphic Governance Bridge
Bridges Polymorphic Schema events to Predictive Impact, Task Reconciliation,
Autonomous Mission Loop, Decision Calibration, and Experience Memory.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Set

from agents.polymorphic_schema.models import (
    PolymorphicDriftReport,
    PolymorphicSchema,
    SchemaVariant,
    VariantDiff,
)


class PolymorphicGovernanceBridge:
    """Inter-system bridge propagating polymorphic schema events across JARVIS OS subsystems."""

    @classmethod
    def integrate_polymorphic_schema(
        cls,
        polymorphic_schema: PolymorphicSchema,
        semantic_graph: Any = None,
    ) -> Dict[str, Any]:
        """Integrates a validated or inferred polymorphic schema into the CrossLanguageSemanticGraph."""
        nodes_updated = 0
        if semantic_graph and polymorphic_schema:
            from agents.semantic_graph.models import SemanticNode, SemanticEdge, SemanticNodeType, SemanticRelationType
            union_node_id = f"node_union_{polymorphic_schema.schema_id}"
            semantic_graph.add_node(
                SemanticNode(
                    node_id=union_node_id,
                    node_type=SemanticNodeType.API_ENDPOINT,
                    language="CROSS_LANGUAGE",
                    source_ref=polymorphic_schema.route or "/api/polymorphic",
                    symbol=polymorphic_schema.schema_id,
                )
            )
            nodes_updated += 1
            for v in polymorphic_schema.variants:
                v_node_id = f"node_variant_{v.variant_id}"
                semantic_graph.add_node(
                    SemanticNode(
                        node_id=v_node_id,
                        node_type=SemanticNodeType.DATA_MODEL,
                        language="CROSS_LANGUAGE",
                        source_ref=polymorphic_schema.route or "/api/polymorphic",
                        symbol=v.label,
                    )
                )
                nodes_updated += 1
                semantic_graph.add_edge(
                    SemanticEdge(
                        edge_id=f"edge_{union_node_id}_{v_node_id}",
                        source_id=union_node_id,
                        target_id=v_node_id,
                        relation=SemanticRelationType.EXPOSES,
                    )
                )
        return {
            "status": "INTEGRATED",
            "schema_id": polymorphic_schema.schema_id if polymorphic_schema else "",
            "nodes_updated": nodes_updated,
        }

    @classmethod
    def generate_reconciliation_tasks(cls, drift_report: PolymorphicDriftReport) -> List[Dict[str, Any]]:
        """Generates causal tasks in Task Reconciliation (Phase 39.2) based on polymorphic drift."""
        tasks: List[Dict[str, Any]] = []
        base_id = drift_report.contract_id

        for diff in drift_report.diffs:
            if diff.diff_type.value == "VARIANT_ADDED":
                tasks.append({
                    "task_id": f"tsk_recon_{base_id}_variant_added_{diff.variant_id}",
                    "type": "UPDATE_CONSUMER_VARIANT",
                    "title": f"Handle new polymorphic variant '{diff.variant_id}' on endpoint '{base_id}'",
                    "priority": "NORMAL",
                    "causal_origin": f"POLY_DRIFT:{drift_report.drift_id}",
                    "derived_from": diff.variant_id,
                    "dependencies": [],
                })
            elif diff.diff_type.value == "VARIANT_REMOVED":
                tasks.append({
                    "task_id": f"tsk_recon_{base_id}_variant_removed_{diff.variant_id}",
                    "type": "MIGRATE_REMOVED_VARIANT",
                    "title": f"Migrate consumers off removed variant '{diff.variant_id}' on '{base_id}'",
                    "priority": "CRITICAL",
                    "causal_origin": f"POLY_DRIFT:{drift_report.drift_id}",
                    "derived_from": diff.variant_id,
                    "dependencies": [],
                })
            elif diff.diff_type.value in ("DISCRIMINATOR_CHANGED", "DISCRIMINATOR_REMOVED"):
                tasks.append({
                    "task_id": f"tsk_recon_{base_id}_discriminator_update",
                    "type": "ADAPT_DISCRIMINATOR",
                    "title": f"Adapt discriminator parsing for polymorphic contract '{base_id}'",
                    "priority": "HIGH",
                    "causal_origin": f"POLY_DRIFT:{drift_report.drift_id}",
                    "dependencies": [],
                })

        # Add validation test revalidation task
        if tasks:
            tasks.append({
                "task_id": f"tsk_recon_{base_id}_revalidate_poly_tests",
                "type": "REVALIDATE_POLYMORPHIC_TEST",
                "title": f"Revalidate cross-language union test suite for '{base_id}'",
                "priority": "HIGH",
                "causal_origin": f"POLY_DRIFT:{drift_report.drift_id}",
                "dependencies": [t["task_id"] for t in tasks if "revalidate" not in t["task_id"]],
            })

        return tasks

    @classmethod
    def project_predictive_impact(
        cls,
        polymorphic_schema: PolymorphicSchema,
        drift_report: PolymorphicDriftReport,
    ) -> Dict[str, Any]:
        """Projects downstream file and task impact using the Predictive Impact Engine (Phase 39)."""
        predicted_files: Set[str] = set()
        c_id = polymorphic_schema.contract_id

        # Normalize endpoint path to files
        endpoint_clean = c_id.replace("ctr_", "").replace("api_", "")
        predicted_files.add(f"frontend/src/api/{endpoint_clean}.ts")
        predicted_files.add(f"backend/routers/{endpoint_clean}.py")
        predicted_files.add(f"tests/test_{endpoint_clean}.py")

        for impact in drift_report.affected_consumers:
            if impact.consumer_type == "FRONTEND_COMPONENT":
                predicted_files.add(f"frontend/src/components/{impact.consumer_id}")
            elif impact.consumer_type == "TEST":
                predicted_files.add(f"tests/{impact.consumer_id}")

        return {
            "drift_id": drift_report.drift_id,
            "contract_id": c_id,
            "classification": drift_report.classification,
            "predicted_files": sorted(list(predicted_files)),
            "new_variants_count": len(drift_report.new_variants),
            "removed_variants_count": len(drift_report.removed_variants),
            "confidence": drift_report.confidence,
        }

    @classmethod
    def create_experience_record(
        cls,
        variant_id: str,
        contract_id: str,
        contract_version: str,
        resolution_action: str,
        outcome: str,
    ) -> Dict[str, Any]:
        """Creates an experience memory record explicitly scoped to a variant (Fases 42/43)."""
        return {
            "record_id": f"exp_poly_{uuid.uuid4().hex[:8]}",
            "variant_id": variant_id,
            "contract_id": contract_id,
            "contract_version": contract_version,
            "resolution_action": resolution_action,
            "outcome": outcome,
            "applicability_constraint": f"Strictly scoped to variant '{variant_id}'. Not applicable to other variants.",
            "timestamp": time.time(),
        }

    @classmethod
    def build_decision_trace(
        cls,
        polymorphic_schema_id: str,
        variant_detected: str,
        discriminator_field: Optional[str],
        drift_classification: str,
        policy_rule: str,
        decision: str,
    ) -> Dict[str, Any]:
        """Produces a DecisionTrace entry for Phase 41 Decision Calibration."""
        return {
            "trace_id": f"dec_poly_{uuid.uuid4().hex[:8]}",
            "polymorphic_schema_id": polymorphic_schema_id,
            "variant_detected": variant_detected,
            "discriminator": discriminator_field,
            "drift_classification": drift_classification,
            "policy_rule": policy_rule,
            "decision": decision,
            "timestamp": time.time(),
        }
