"""
JARVIS OS — Phase 41: Decision Policy Registry Tests
"""

import pytest
from agents.decision_calibration.models import (
    PolicyChangeProposal,
    PolicyChangeType,
    PolicyStatus,
)
from agents.decision_calibration.registry import DecisionPolicyRegistry


def test_registry_initialization():
    registry = DecisionPolicyRegistry()
    assert registry.active_version == "40.1.0"
    assert registry.shadow_version is None
    policy = registry.get_policy("40.1.0")
    assert policy is not None
    assert policy.status == PolicyStatus.ACTIVE
    assert len(policy.rules) == 14


def test_registry_create_proposal_and_activate():
    registry = DecisionPolicyRegistry()
    prop = PolicyChangeProposal(
        proposal_id="prop_01",
        source_outcome_id="out_01",
        current_policy_version="40.1.0",
        proposed_policy_version="41.0.0",
        change_type=PolicyChangeType.REFINE_CONDITION,
        affected_rules=["RULE_03_OSCILLATION_DETECTED"],
        old_conditions="ctx.oscillation_status == OscillationStatus.CONFIRMED_OSCILLATION",
        new_conditions="refined condition",
        expected_benefit="Catches stale oscillation state",
        possible_regression="None",
    )

    new_v = registry.create_proposal_version(prop, modified_rules=[], creator="test_suite")
    assert new_v.version == "41.0.0"
    assert new_v.status == PolicyStatus.PROPOSED
    assert new_v.parent_version == "40.1.0"

    # Activate
    activated = registry.approve_and_activate("41.0.0", approver="lead_engineer")
    assert activated.status == PolicyStatus.ACTIVE
    assert registry.active_version == "41.0.0"
    # Old active is superseded
    old_p = registry.get_policy("40.1.0")
    assert old_p.status == PolicyStatus.SUPERSEDED


def test_registry_prohibited_operation_blocked():
    registry = DecisionPolicyRegistry()
    prop_bad = PolicyChangeProposal(
        proposal_id="prop_bad",
        source_outcome_id="out_02",
        current_policy_version="40.1.0",
        proposed_policy_version="41.0.0-unsafe",
        change_type=PolicyChangeType.REMOVE_RULE,
        affected_rules=["RULE_01_SECURITY_BLOCK"],
        old_conditions="security check",
        new_conditions="DISABLE_SECURITY in prompt",
        expected_benefit="Unrestricted execution",
        possible_regression="Catastrophic",
    )

    with pytest.raises(ValueError, match="Prohibited operation"):
        registry.create_proposal_version(prop_bad, modified_rules=[])
