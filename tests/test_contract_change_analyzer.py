"""
Tests for Phase 48 ContractChangeAnalyzer:
- Task change analysis
- Risk classification (SAFE, NON_BREAKING, BREAKING)
- Pre-execution simulation read-only invariant (state_before == state_after)
"""

import pytest
from agents.contract_change_management.analyzer import ContractChangeAnalyzer
from agents.contract_change_management.models import (
    ContractChangeType,
    ContractRiskLevel,
)


def test_analyze_breaking_avatar_change():
    task = {
        "id": "tsk_user_avatar",
        "title": "Update user avatar from string to object with dimensions",
        "description": "Convert avatar primitive string into { url, width, height } object",
    }
    pred = ContractChangeAnalyzer.analyze_task_change(
        task=task,
        predicted_files=["backend/api/users.py", "frontend/src/components/UserCard.tsx"],
    )

    assert pred.breaking_risk == ContractRiskLevel.BREAKING
    assert pred.migration_required is True
    assert pred.approval_required is True
    assert len(pred.predicted_diffs) == 1
    assert pred.predicted_diffs[0].change_type == ContractChangeType.CHANGE_FIELD_TYPE
    assert pred.predicted_diffs[0].field_path == "avatar"
    assert pred.migration_plan is not None


def test_analyze_non_breaking_optional_field():
    task = {
        "id": "tsk_add_tier",
        "title": "Add optional user_tier field to user profile",
        "description": "Add optional user_tier property to payload response",
    }
    pred = ContractChangeAnalyzer.analyze_task_change(
        task=task,
        predicted_files=["backend/api/users.py"],
    )

    assert pred.breaking_risk == ContractRiskLevel.NON_BREAKING
    assert pred.migration_required is False
    assert pred.approval_required is False
    assert len(pred.predicted_diffs) == 1
    assert pred.predicted_diffs[0].change_type == ContractChangeType.ADD_OPTIONAL_FIELD


def test_analyze_breaking_field_removal():
    task = {
        "id": "tsk_remove_token",
        "title": "Remove field legacy_token from user object",
        "description": "Delete field legacy_token from response payload",
    }
    pred = ContractChangeAnalyzer.analyze_task_change(
        task=task,
        predicted_files=["backend/api/users.py"],
    )

    assert pred.breaking_risk == ContractRiskLevel.BREAKING
    assert pred.migration_required is True
    assert any(d.change_type == ContractChangeType.REMOVE_FIELD for d in pred.predicted_diffs)


def test_simulation_read_only_invariant():
    current_contract = {
        "contract_id": "contract_users_v1",
        "version": "1.0.0",
        "schema": {
            "id": "string",
            "name": "string",
            "avatar": "string",
        },
    }
    predicted_contract = {
        "contract_id": "contract_users_v1",
        "version": "2.0.0",
        "schema": {
            "id": "string",
            "name": "string",
            "avatar": {"url": "string", "width": "int", "height": "int"},
        },
    }

    # Execute simulation
    sim = ContractChangeAnalyzer.simulate_pre_execution_diff(
        current_contract=current_contract,
        predicted_contract=predicted_contract,
    )

    assert sim.is_read_only is True
    assert sim.state_before_hash == sim.state_after_hash
    assert sim.diff_verdict == ContractRiskLevel.BREAKING
    assert len(sim.details["diff_items"]) >= 1
    # Verify original input contract object was not modified in-place
    assert current_contract["schema"]["avatar"] == "string"
