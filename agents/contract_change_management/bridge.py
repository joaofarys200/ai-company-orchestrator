"""
JARVIS OS — Phase 48: Contract-Aware Autonomous Change Management
ContractAwareChangeBridge: Bridges contract change management with the Autonomous Engineering Loop,
Predictive Impact, Task Reconciliation, Decision Trace, and Cross-Language Semantic Graph.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from agents.contract_change_management.analyzer import ContractChangeAnalyzer
from agents.contract_change_management.gate import ContractMissionGate
from agents.contract_change_management.models import (
    ContractChangePrediction,
    ContractRiskLevel,
    ContractVerificationResult,
    GateDecision,
)
from agents.contract_change_management.security import ContractChangeSecuritySentinel
from agents.contract_change_management.verification import ContractRuntimeVerifier


class ContractAwareChangeBridge:
    """
    Orchestrates integration across the entire JARVIS intelligence stack,
    enforcing that contract awareness precedes execution in the autonomous loop.
    """

    @classmethod
    def evaluate_task_preflight(
        cls,
        task: dict[str, Any],
        predicted_files: list[str],
        semantic_graph: Optional[Any] = None,
        contract_baselines: Optional[dict[str, Any]] = None,
        polymorphic_schemas: Optional[dict[str, Any]] = None,
        operator_signature: Optional[str] = None,
    ) -> tuple[ContractChangePrediction, GateDecision, bool, str]:
        """
        Runs complete preflight:
        1. Analyzes contract impact
        2. Audits security invariants
        3. Evaluates admission gate
        Returns: (prediction, gate_decision, allowed_to_execute, reason)
        """
        # 1. Analyze task change
        prediction = ContractChangeAnalyzer.analyze_task_change(
            task=task,
            predicted_files=predicted_files,
            semantic_graph=semantic_graph,
            contract_baselines=contract_baselines,
            polymorphic_schemas=polymorphic_schemas,
        )

        # 2. Security audit
        is_sec_ok, sec_reason = ContractChangeSecuritySentinel.audit_security_invariants(
            [d.to_dict() for d in prediction.predicted_diffs]
        )
        if not is_sec_ok:
            return (
                prediction,
                GateDecision.BLOCK,
                False,
                sec_reason,
            )

        # 3. Gate evaluation
        is_approved = ContractChangeSecuritySentinel.validate_approval_signature(operator_signature)
        decision, allowed, reason = ContractMissionGate.evaluate_preflight_gate(
            prediction=prediction,
            human_approved=is_approved,
        )

        return prediction, decision, allowed, reason

    @classmethod
    def verify_contract_completion(
        cls,
        contract_id: str,
        predicted_version: str,
        observed_schema: dict[str, Any],
        observed_version: str,
        consumer_results: dict[str, bool],
        test_passed: bool = True,
        browser_passed: bool = True,
        evidence_present: bool = True,
    ) -> tuple[ContractVerificationResult, bool, str]:
        """
        Performs post-execution verification and evaluates the Completion Gate.
        Returns: (verification_result, completion_allowed, reason)
        """
        ver_result = ContractRuntimeVerifier.verify_runtime_execution(
            contract_id=contract_id,
            predicted_version=predicted_version,
            actual_observed_schema=observed_schema,
            actual_observed_version=observed_version,
            consumer_check_results=consumer_results,
            test_results_passed=test_passed,
            browser_qa_passed=browser_passed,
            evidence_present=evidence_present,
        )

        gate_passed, gate_reason = ContractMissionGate.evaluate_completion_gate(ver_result)
        return ver_result, gate_passed, gate_reason

    @classmethod
    def enrich_decision_trace(
        cls,
        decision_trace: Any,
        prediction: ContractChangePrediction,
        gate_decision: GateDecision,
    ) -> None:
        """
        Enriches DecisionTrace (Phase 41) with contract change intelligence.
        """
        if hasattr(decision_trace, "contract_analysis"):
            setattr(decision_trace, "contract_analysis", {
                "prediction_id": prediction.prediction_id,
                "affected_contracts": prediction.affected_contracts,
                "breaking_risk": prediction.breaking_risk.value,
                "migration_required": prediction.migration_required,
                "approval_required": prediction.approval_required,
            })
        if hasattr(decision_trace, "consumer_impact"):
            setattr(decision_trace, "consumer_impact", [c.to_dict() for c in prediction.affected_consumers])
        if hasattr(decision_trace, "migration_id"):
            mig_id = prediction.migration_plan.migration_id if prediction.migration_plan else None
            setattr(decision_trace, "migration_id", mig_id)
        if hasattr(decision_trace, "contract_risk"):
            setattr(decision_trace, "contract_risk", prediction.breaking_risk.value)
        if hasattr(decision_trace, "gate_result"):
            setattr(decision_trace, "gate_result", gate_decision.value)
