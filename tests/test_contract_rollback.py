"""
Tests for Phase 48 Deterministic Contract Rollback:
- Reverting to source_contract_version
- Preserving audit history and migration records
- Contract registry version update
"""

import pytest
from agents.contract_change_management.migration import ContractMigrationEngine
from agents.contract_change_management.models import ContractRiskLevel
from agents.contract_change_management.verification import ContractRuntimeVerifier


def test_deterministic_rollback():
    plan = ContractMigrationEngine.formulate_migration_plan(
        contract_id="contract_users_v1",
        current_version="1.0.0",
        proposed_version="2.0.0",
        risk_level=ContractRiskLevel.BREAKING,
        affected_consumers=[],
    )
    plan.status = "APPROVED"

    registry = {
        "contract_users_v1": {
            "active_version": "2.0.0",
            "version_history": [{"action": "UPGRADE", "version": "2.0.0"}],
        }
    }

    rollback_res = ContractRuntimeVerifier.execute_deterministic_rollback(
        migration_plan=plan,
        current_contract_registry=registry,
    )

    assert rollback_res["status"] == "SUCCESS"
    assert rollback_res["restored_version"] == "1.0.0"
    assert plan.status == "ROLLED_BACK"
    assert registry["contract_users_v1"]["active_version"] == "1.0.0"

    history = registry["contract_users_v1"]["version_history"]
    assert len(history) == 2
    assert history[-1]["action"] == "ROLLBACK"
    assert history[-1]["restored_to"] == "1.0.0"
