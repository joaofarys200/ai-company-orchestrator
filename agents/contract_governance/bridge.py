"""
JARVIS OS — Phase 46: Contract Governance Bridge
Connects Contract Drift events to Predictive Impact (Phase 39), Task Reconciliation (Phase 39.2),
Autonomous Mission Loop (Phase 40), Decision Calibration (Phase 41), and Experience Memory (Phases 42/43).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.contract_governance.models import (
    ContractDriftReport,
    DriftClassification,
    DriftPolicyAction,
    DriftResolution,
)


class ContractGovernanceBridge:
    """Inter-system bridge propagating contract governance events across JARVIS OS subsystems."""

    @classmethod
    def generate_reconciliation_tasks(cls, drift_report: ContractDriftReport) -> List[Dict[str, Any]]:
        """Generates causal tasks in Task Reconciliation (Phase 39.2) based on observed drift."""
        tasks: List[Dict[str, Any]] = []
        base_id = drift_report.contract_id

        if drift_report.classification == DriftClassification.NON_BREAKING:
            tasks.append({
                "task_id": f"tsk_recon_{base_id}_monitor",
                "type": "MONITOR_CONTRACT",
                "title": f"Monitor non-breaking variation on contract '{base_id}'",
                "priority": "LOW",
                "causal_origin": f"DRIFT:{drift_report.drift_id}",
                "dependencies": [],
            })
        elif drift_report.classification in (DriftClassification.POTENTIALLY_BREAKING, DriftClassification.BREAKING):
            # Task 1: Update formal contract
            tasks.append({
                "task_id": f"tsk_recon_{base_id}_update_contract",
                "type": "UPDATE_CONTRACT",
                "title": f"Draft and review versioned contract evolution for '{base_id}'",
                "priority": "HIGH",
                "causal_origin": f"DRIFT:{drift_report.drift_id}",
                "dependencies": [],
            })

            # Task 2: Update consumers
            for consumer in drift_report.affected_consumers:
                tasks.append({
                    "task_id": f"tsk_recon_{consumer.consumer_id}_update",
                    "type": "UPDATE_CONSUMER",
                    "title": f"Update downstream consumer '{consumer.consumer_id}' ({consumer.consumer_type}) to match contract revision",
                    "priority": "HIGH",
                    "causal_origin": f"DRIFT:{drift_report.drift_id}",
                    "dependencies": [f"tsk_recon_{base_id}_update_contract"],
                })

            # Task 3: Migration
            tasks.append({
                "task_id": f"tsk_recon_{base_id}_migration",
                "type": "ADD_MIGRATION",
                "title": f"Generate schema migration and compatibility shim for '{base_id}'",
                "priority": "MEDIUM",
                "causal_origin": f"DRIFT:{drift_report.drift_id}",
                "dependencies": [f"tsk_recon_{base_id}_update_contract"],
            })

            # Task 4: Revalidate tests and browser
            tasks.append({
                "task_id": f"tsk_recon_{base_id}_revalidate_tests",
                "type": "REVALIDATE_TEST",
                "title": f"Re-run automated pytest suites for '{base_id}'",
                "priority": "MEDIUM",
                "causal_origin": f"DRIFT:{drift_report.drift_id}",
                "dependencies": [f"tsk_recon_{base_id}_update_contract"],
            })
            tasks.append({
                "task_id": f"tsk_recon_{base_id}_browser_qa",
                "type": "BROWSER_REVALIDATION",
                "title": f"Verify E2E browser scenarios for '{base_id}' in Microsoft Edge",
                "priority": "MEDIUM",
                "causal_origin": f"DRIFT:{drift_report.drift_id}",
                "dependencies": [f"tsk_recon_{base_id}_revalidate_tests"],
            })

        return tasks

    @classmethod
    def predict_impact(cls, drift_report: ContractDriftReport) -> Dict[str, Any]:
        """Maps drift into Predictive Impact Engine (Phase 39) structure."""
        predicted_files: List[str] = []
        for consumer in drift_report.affected_consumers:
            if consumer.consumer_type == "FRONTEND_COMPONENT":
                predicted_files.append(f"frontend/src/features/{consumer.consumer_id}.tsx")
            elif consumer.consumer_type == "BACKEND_SERVICE":
                predicted_files.append(f"backend/api/{consumer.consumer_id}.py")
            elif consumer.consumer_type == "TEST":
                predicted_files.append(f"tests/test_{consumer.consumer_id}.py")

        return {
            "prediction_id": f"pred_drift_{drift_report.drift_id}",
            "scope": "CROSS_MODULE" if len(drift_report.affected_consumers) > 1 else "LOCAL",
            "predicted_files": predicted_files,
            "affected_consumers_count": len(drift_report.affected_consumers),
            "risk": "HIGH" if drift_report.classification == DriftClassification.BREAKING else "LOW",
            "classification": drift_report.classification.value,
            "requires_pause": drift_report.classification == DriftClassification.BREAKING,
        }

    @classmethod
    def build_experience_record(
        cls,
        drift_report: ContractDriftReport,
        resolution: DriftResolution,
    ) -> Dict[str, Any]:
        """Creates an ExperienceRecord (Phase 42/43) when drift is resolved."""
        return {
            "record_id": f"exp_drift_{resolution.resolution_id}",
            "type": "CONTRACT_DRIFT_RESOLUTION",
            "contract_id": drift_report.contract_id,
            "drift_classification": drift_report.classification.value,
            "affected_consumers": [c.to_dict() for c in drift_report.affected_consumers],
            "action_taken": resolution.action.value,
            "version_before": resolution.contract_version_before,
            "version_after": resolution.contract_version_after,
            "outcome": resolution.outcome,
            "timestamp": resolution.timestamp,
        }

    @classmethod
    def build_decision_trace(
        cls,
        drift_report: ContractDriftReport,
        decision_action: str,
    ) -> Dict[str, Any]:
        """Creates an audit entry for Decision Calibration (Phase 41)."""
        return {
            "trace_id": f"dtrace_drift_{drift_report.drift_id}",
            "drift_id": drift_report.drift_id,
            "drift_classification": drift_report.classification.value,
            "policy_rule": f"RULE_{drift_report.classification.value}_DRIFT",
            "decision": decision_action,
            "recommended_action": drift_report.recommended_action.value,
            "calibrated": True,
            "timestamp": time.time(),
        }
