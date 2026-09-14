"""
JARVIS OS — Phase 41: Policy Proposal Engine Tests
"""

import pytest
from agents.autonomous_loop.models import LoopDecisionType
from agents.decision_calibration.models import (
    DecisionCorrectness,
    DecisionErrorTaxonomy,
    DecisionOutcome,
    PolicyChangeProposal,
    PolicyChangeType,
)
from agents.decision_calibration.proposer import PolicyProposalEngine


def test_formulate_proposal_from_observation_gap():
    outcome = DecisionOutcome(
        outcome_id="out_osc_191",
        mission_id="m_osc",
        cycle_id="c_1",
        decision_id="dec_191",
        decision_type=LoopDecisionType.CONTINUE,
        policy_version="40.1.0",
        rule_id="RULE_14_NORMAL_PROGRESSION",
        expected_outcome="REQUEST_HUMAN",
        observed_outcome="Oscillation undetected in decision step",
        decision_correctness=DecisionCorrectness.INCORRECT,
        root_cause=DecisionErrorTaxonomy.OBSERVATION_GAP,
    )

    prop = PolicyProposalEngine.formulate_proposal_from_outcome(outcome)
    assert prop is not None
    assert prop.change_type == PolicyChangeType.REFINE_CONDITION
    assert "RULE_03_OSCILLATION_DETECTED" in prop.affected_rules
    assert prop.requires_human_review is True


def test_prohibit_unsafe_proposals():
    prop = PolicyChangeProposal(
        proposal_id="prop_hack",
        source_outcome_id="out_0",
        current_policy_version="40.1.0",
        proposed_policy_version="41.0.0",
        change_type=PolicyChangeType.REMOVE_RULE,
        affected_rules=["RULE_01"],
        old_conditions="",
        new_conditions="BYPASS_MISSION_GATE",
        expected_benefit="",
        possible_regression="",
    )

    is_safe, msg = PolicyProposalEngine.validate_safety_invariants(prop)
    assert is_safe is False
    assert "Permanent safety block" in msg or "Prohibited operation" in msg
