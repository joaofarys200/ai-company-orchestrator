"""
JARVIS OS — Phase 46: Predictive Impact & Downstream Integration Test Suite
Validates causal generation of tasks, predictive file impacts, and experience memory records.
"""

from agents.contract_governance.bridge import ContractGovernanceBridge
from agents.contract_governance.models import (
    ConsumerImpact,
    ConsumerImpactLevel,
    ContractDriftReport,
    DriftClassification,
    DriftPolicyAction,
    DriftResolution,
    DriftResolutionAction,
)


def test_predictive_impact_mapping():
    rep = ContractDriftReport(
        drift_id="drift_integ_01",
        contract_id="ctr_users",
        baseline_version="1.0.0",
        observed_version="2.0.0",
        classification=DriftClassification.BREAKING,
        affected_consumers=[
            ConsumerImpact(consumer_id="SearchBox", consumer_type="FRONTEND_COMPONENT", impact_level=ConsumerImpactLevel.DIRECT, description="Search UI"),
            ConsumerImpact(consumer_id="users_service", consumer_type="BACKEND_SERVICE", impact_level=ConsumerImpactLevel.DIRECT, description="FastAPI service"),
        ],
    )

    pred = ContractGovernanceBridge.predict_impact(rep)
    assert pred["scope"] == "CROSS_MODULE"
    assert pred["risk"] == "HIGH"
    assert pred["requires_pause"] is True
    assert any("SearchBox.tsx" in f for f in pred["predicted_files"])
    assert any("users_service.py" in f for f in pred["predicted_files"])


def test_reconciliation_tasks_generation():
    rep = ContractDriftReport(
        drift_id="drift_integ_02",
        contract_id="ctr_orders",
        baseline_version="1.0.0",
        observed_version="2.0.0",
        classification=DriftClassification.BREAKING,
        affected_consumers=[
            ConsumerImpact(consumer_id="OrderCheckout", consumer_type="FRONTEND_COMPONENT", impact_level=ConsumerImpactLevel.DIRECT, description="Checkout UI"),
        ],
    )

    tasks = ContractGovernanceBridge.generate_reconciliation_tasks(rep)
    assert len(tasks) >= 4
    task_types = [t["type"] for t in tasks]
    assert "UPDATE_CONTRACT" in task_types
    assert "UPDATE_CONSUMER" in task_types
    assert "ADD_MIGRATION" in task_types
    assert "REVALIDATE_TEST" in task_types
    assert "BROWSER_REVALIDATION" in task_types

    # Invariant: Causal trace back to drift_id
    assert all("DRIFT:drift_integ_02" in t["causal_origin"] for t in tasks)


def test_experience_and_decision_trace():
    rep = ContractDriftReport(
        drift_id="drift_integ_03",
        contract_id="ctr_auth",
        baseline_version="1.0.0",
        observed_version="1.1.0",
        classification=DriftClassification.NON_BREAKING,
        recommended_action=DriftPolicyAction.MONITOR,
    )
    res = DriftResolution(
        resolution_id="res_03",
        drift_id="drift_integ_03",
        contract_id="ctr_auth",
        action=DriftResolutionAction.MONITOR,
        contract_version_before="1.0.0",
        contract_version_after="1.0.0",
        outcome="Monitored in production",
    )

    exp = ContractGovernanceBridge.build_experience_record(rep, res)
    assert exp["type"] == "CONTRACT_DRIFT_RESOLUTION"
    assert exp["contract_id"] == "ctr_auth"

    dtrace = ContractGovernanceBridge.build_decision_trace(rep, decision_action="CONTINUE_MONITORING")
    assert dtrace["drift_id"] == "drift_integ_03"
    assert dtrace["calibrated"] is True
