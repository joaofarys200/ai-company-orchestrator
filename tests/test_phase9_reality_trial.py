"""
PyTest Test Suite for Phase 9 Reality-to-Production Trial
"""

import asyncio
import pytest
from agents.reality_production_agent import (
    RealityProductionAgent,
    FinancialVerificationProvider,
    EvidenceTier,
    EconomicStateV2,
    EconomicDecisionMetrics
)


def test_evidence_tiers_and_hierarchy():
    tiers = [
        EvidenceTier.SIMULATED,
        EvidenceTier.LOCAL_SYNTHETIC,
        EvidenceTier.TEST_FIXTURE,
        EvidenceTier.EXTERNAL_OBSERVED,
        EvidenceTier.EXTERNAL_VERIFIED,
        EvidenceTier.FINANCIAL_TRANSACTION_VERIFIED
    ]
    assert len(tiers) == 6


def test_financial_verification_provider_fixture_demotion():
    # Test Fixture simulation must be demoted to TEST_FIXTURE and yield $0.00 revenue
    provider = FinancialVerificationProvider(is_live_gateway=False)
    tx_data = {"transaction_id": "tx_mock_123", "amount": 299.00, "is_test_mode": True, "is_settled": False}
    valid, tier, verified_revenue = provider.verify_transaction(tx_data, "any_sig")
    assert valid is True
    assert tier == EvidenceTier.TEST_FIXTURE
    assert verified_revenue == 0.00


def test_financial_verification_provider_live_settlement():
    provider = FinancialVerificationProvider(is_live_gateway=True)
    tx_data = {"transaction_id": "tx_live_778", "amount": 199.00, "is_test_mode": False, "is_settled": True}
    import hmac, hashlib, json
    payload = json.dumps(tx_data, sort_keys=True)
    sig = hmac.new(provider.HMAC_AUDIT_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    
    valid, tier, verified_revenue = provider.verify_transaction(tx_data, sig)
    assert valid is True
    assert tier == EvidenceTier.FINANCIAL_TRANSACTION_VERIFIED
    assert verified_revenue == 199.00


def test_budget_authorization_limits():
    agent = RealityProductionAgent()
    max_budget, max_single, max_daily = agent.check_budget_authorization()
    assert max_budget == 0.00
    assert max_single == 0.00
    assert max_daily == 0.00


def test_decision_metrics_calculation():
    agent = RealityProductionAgent()
    m = agent.calculate_decision_metrics(
        tam_customers=1000,
        wtp_monthly=100.0,
        cac=200.0,
        churn_rate=0.05,
        conv_rate=0.02
    )
    assert m.retention_months == 20.0
    assert m.ltv == 2000.0
    assert m.gross_margin == 0.90  # (2000 - 200) / 2000
    assert m.payback_period_months == 2.0  # 200 / 100
    assert m.expected_value == 36000.0  # (1000 * 0.02) * (2000 - 200)
    assert m.risk_adjusted_ev == 23400.0  # 36000 * 0.65


def test_reality_production_agent_trial_execution():
    async def _run():
        agent = RealityProductionAgent()
        result = await agent.execute_trial()
        
        # 1. Verify 10-state progression
        assert len(result.state_transitions) == 10
        assert result.state_transitions[0] == EconomicStateV2.IDEA
        assert result.state_transitions[-1] == EconomicStateV2.PAYMENT_CONFIRMED
        
        # 2. Strict Reality Invariants
        assert result.budget_spent_usd == 0.00
        assert result.verified_revenue_usd == 0.00
        assert result.synthetic_revenue_blocked_usd == 199.00
        assert result.pivots_count == 2
        assert result.computer_use_record.screenshot_sha256 is not None
        assert result.verdict == "REAL_WORLD_VALIDATION_ONLY"

    asyncio.run(_run())
