"""
Tests for Phase 48 Preflight Gate (ContractMissionGate & ContractAwareChangeBridge):
- Admission control before execution
- Breaking change blocked without approved plan
- Approval signature validation
- Security and Economic invariant enforcement
"""

import pytest
from agents.contract_change_management.bridge import ContractAwareChangeBridge
from agents.contract_change_management.gate import ContractMissionGate
from agents.contract_change_management.models import (
    ContractChangePrediction,
    ContractChangeType,
    ContractRiskLevel,
    GateDecision,
    PredictedContractDiff,
)
from agents.contract_change_management.migration import ContractMigrationEngine


def test_preflight_blocks_unapproved_breaking_change():
    pred = ContractChangePrediction(
        prediction_id="pred_break_01",
        task_id="tsk_break_01",
        breaking_risk=ContractRiskLevel.BREAKING,
        approval_required=True,
        migration_plan=ContractMigrationEngine.formulate_migration_plan(
            contract_id="contract_test",
            current_version="1.0.0",
            proposed_version="2.0.0",
            risk_level=ContractRiskLevel.BREAKING,
            affected_consumers=[],
        ),
    )

    decision, allowed, reason = ContractMissionGate.evaluate_preflight_gate(
        prediction=pred,
        human_approved=False,
    )
    assert decision == GateDecision.REQUIRE_HUMAN_APPROVAL
    assert allowed is False
    assert "requires explicit human approval" in reason


def test_preflight_allows_approved_breaking_change():
    pred = ContractChangePrediction(
        prediction_id="pred_break_02",
        task_id="tsk_break_02",
        breaking_risk=ContractRiskLevel.BREAKING,
        approval_required=True,
        migration_plan=ContractMigrationEngine.formulate_migration_plan(
            contract_id="contract_test",
            current_version="1.0.0",
            proposed_version="2.0.0",
            risk_level=ContractRiskLevel.BREAKING,
            affected_consumers=[],
        ),
    )

    decision, allowed, reason = ContractMissionGate.evaluate_preflight_gate(
        prediction=pred,
        human_approved=True,
    )
    assert decision == GateDecision.ALLOW
    assert allowed is True


def test_preflight_blocks_auth_removal_even_if_approved():
    diff_auth = PredictedContractDiff(
        diff_id="diff_auth_bad",
        contract_id="contract_auth",
        contract_version="1.0.0",
        proposed_version="2.0.0",
        change_type=ContractChangeType.CHANGE_AUTH,
        field_path="auth.bearer_token",
        old_definition="Required",
        new_definition="None",
        risk_level=ContractRiskLevel.BREAKING,
        reason="Security removal",
    )
    pred = ContractChangePrediction(
        prediction_id="pred_auth_sec",
        task_id="tsk_auth_sec",
        predicted_diffs=[diff_auth],
        breaking_risk=ContractRiskLevel.BREAKING,
    )

    decision, allowed, reason = ContractMissionGate.evaluate_preflight_gate(
        prediction=pred,
        human_approved=True,
    )
    assert decision == GateDecision.BLOCK
    assert allowed is False
    assert "Security contract violation" in reason


def test_bridge_evaluate_task_preflight():
    task = {
        "id": "tsk_avatar_bridge",
        "title": "Convert avatar string to rich object in User API",
        "description": "Avatar object struct conversion",
    }
    pred, decision, allowed, reason = ContractAwareChangeBridge.evaluate_task_preflight(
        task=task,
        predicted_files=["backend/api/users.py"],
        operator_signature="VALID_OPERATOR_SIGNATURE_2026_LEAD",
    )

    assert pred.breaking_risk == ContractRiskLevel.BREAKING
    assert decision == GateDecision.ALLOW
    assert allowed is True
