"""
Tests for Phase 48 ContractMigrationEngine:
- Migration plan generation
- Causal task derivation (backend, consumer, test, browser)
- Rollout and rollback strategy formulation
- Non-breaking changes avoid unnecessary migration tasks
"""

import pytest
from agents.contract_change_management.migration import ContractMigrationEngine
from agents.contract_change_management.models import (
    ConsumerCategory,
    ConsumerPatternMatching,
    ContractConsumerTrace,
    ContractRiskLevel,
    MigrationStrategy,
    RolloutSafetyStrategy,
)


def test_formulate_migration_plan_for_breaking_change():
    consumers = [
        ContractConsumerTrace(
            consumer_id="frontend-user-card",
            name="UserCard Component",
            file_path="frontend/src/components/UserCard.tsx",
            category=ConsumerCategory.DIRECT,
            pattern_matching=ConsumerPatternMatching.CLOSED_EXHAUSTIVE,
            impact_reason="Avatar converted to object",
            required_action="Adapt avatar rendering",
        ),
        ContractConsumerTrace(
            consumer_id="test-user-api",
            name="User API Test Suite",
            file_path="tests/test_user_api.py",
            category=ConsumerCategory.TEST,
            pattern_matching=ConsumerPatternMatching.CLOSED_EXHAUSTIVE,
            impact_reason="Asserts schema shape",
            required_action="Update assertions",
        ),
    ]

    plan = ContractMigrationEngine.formulate_migration_plan(
        contract_id="contract_users_v1",
        current_version="1.0.0",
        proposed_version="2.0.0",
        risk_level=ContractRiskLevel.BREAKING,
        affected_consumers=consumers,
    )

    assert plan.migration_id.startswith("mig_")
    assert plan.source_contract_version == "1.0.0"
    assert plan.target_contract_version == "2.0.0"
    assert plan.compatibility_strategy == MigrationStrategy.MIGRATE_THEN_SWITCH
    assert plan.rollout_strategy == RolloutSafetyStrategy.PREPARE_VALIDATE_MIGRATE_SWITCH
    assert plan.approval_required is True
    assert "RESTORE_ACTIVE_VERSION_1.0.0" in plan.rollback_strategy

    # Check derived tasks
    task_categories = [t.category for t in plan.required_tasks]
    assert "BACKEND" in task_categories
    assert "FRONTEND" in task_categories
    assert "TEST" in task_categories
    assert "BROWSER" in task_categories


def test_non_breaking_migration_plan():
    plan = ContractMigrationEngine.formulate_migration_plan(
        contract_id="contract_products_v1",
        current_version="1.0.0",
        proposed_version="1.1.0",
        risk_level=ContractRiskLevel.NON_BREAKING,
        affected_consumers=[],
    )

    assert plan.compatibility_strategy == MigrationStrategy.BACKWARD_COMPATIBLE
    assert plan.approval_required is False
    assert plan.status == "APPROVED"
