"""
JARVIS OS — Phase 41: Policy Rollback Tests
"""

import pytest
from agents.decision_calibration.models import (
    PolicyChangeProposal,
    PolicyChangeType,
    PolicyStatus,
)
from agents.decision_calibration.registry import DecisionPolicyRegistry


def test_atomic_rollback():
    registry = DecisionPolicyRegistry()
    assert registry.active_version == "40.1.0"

    prop = PolicyChangeProposal(
        proposal_id="prop_41",
        source_outcome_id="out_41",
        current_policy_version="40.1.0",
        proposed_policy_version="41.0.0",
        change_type=PolicyChangeType.REFINE_CONDITION,
        affected_rules=["RULE_03"],
        old_conditions="",
        new_conditions="",
        expected_benefit="Improvement",
        possible_regression="None",
    )
    registry.create_proposal_version(prop, modified_rules=[])
    registry.approve_and_activate("41.0.0", approver="human_lead")
    assert registry.active_version == "41.0.0"

    # Rollback
    rolled_back_to = registry.rollback(operator="incident_commander")
    assert rolled_back_to.version == "40.1.0"
    assert registry.active_version == "40.1.0"

    p41 = registry.get_policy("41.0.0")
    assert p41.status == PolicyStatus.ROLLED_BACK
    assert p41.approval_metadata["rolled_back_by"] == "incident_commander"
