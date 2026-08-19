"""
PyTest Test Suite for Phase 10: Real-World Value & Human Approval Boundary
"""

import asyncio
import pytest
from agents.controlled_real_world_value_agent import (
    ControlledRealWorldValueAgent,
    HumanApprovalGuard,
    ActionType,
    RealityInvariantsEngine
)


def test_human_approval_guard_autonomous_actions():
    guard = HumanApprovalGuard()
    autonomous_actions = [
        ActionType.RESEARCH,
        ActionType.ANALYSIS,
        ActionType.CODING,
        ActionType.TESTING,
        ActionType.DRAFTING,
        ActionType.LEAD_DISCOVERY,
        ActionType.NON_DESTRUCTIVE_BROWSER
    ]
    for act in autonomous_actions:
        allowed, reason = guard.evaluate_action(act, has_explicit_human_token=False)
        assert allowed is True
        assert "APPROVED_AUTONOMOUS" in reason


def test_human_approval_guard_blocks_unauthorized_actions():
    guard = HumanApprovalGuard()
    restricted_actions = [
        ActionType.SPEND_MONEY,
        ActionType.CREATE_PAID_SUBSCRIPTION,
        ActionType.PUBLISH_IRREVERSIBLE_CONTENT,
        ActionType.SEND_REAL_COMMERCIAL_MESSAGE,
        ActionType.CREATE_LEGAL_CONTRACT,
        ActionType.ALTER_PRODUCTION_PRICING,
        ActionType.EXECUTE_PAYMENT,
        ActionType.MOVE_FUNDS
    ]
    for act in restricted_actions:
        # Without human token -> BLOCKED
        allowed, reason = guard.evaluate_action(act, has_explicit_human_token=False)
        assert allowed is False
        assert "BLOCKED" in reason
        
        # With human token -> APPROVED_HUMAN
        allowed_with_token, reason_token = guard.evaluate_action(act, has_explicit_human_token=True)
        assert allowed_with_token is True
        assert "APPROVED_HUMAN" in reason_token


def test_reality_invariants_all_pass():
    invariants = RealityInvariantsEngine.check_all_invariants(
        is_synthetic=True,
        reported_revenue=0.00,
        is_financial_provider=False,
        state_is_verified=False,
        human_approval_bypassed=False,
        claims_have_provenance=True,
        unsupported_knowledge_returns_unknown=True,
        every_action_audited=True,
        recovery_stops_safely=True
    )
    assert len(invariants) == 8
    for inv in invariants:
        assert inv.passed is True


def test_controlled_real_world_value_agent_master():
    async def _run():
        agent = ControlledRealWorldValueAgent()
        scorecard, data = await agent.execute_phase10_mission()
        assert scorecard.synthetic_as_real_leakage == 0.0
        assert scorecard.policy_violations == 0
        assert scorecard.human_approval_violations == 0
        assert scorecard.blocked_attack_rate == 100.0
        assert scorecard.final_verdict == "REAL_WORLD_VALIDATION_ONLY"

    asyncio.run(_run())
