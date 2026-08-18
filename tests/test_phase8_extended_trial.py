"""
PyTest Test Suite for Phase 8 Extended Autonomous Mission Trial
"""

import asyncio
import pytest
from agents.extended_autonomous_mission_agent import (
    ExtendedAutonomousMissionAgent,
    MissionAKnowledgeExecutor,
    MissionBSoftwareEngineeringExecutor,
    MissionCEconomicExecutor,
    ChaosFaultInjector,
    LongHorizonWatchdog,
    CrossMissionMemoryTransfer,
    EconomicState,
    ChaosFaultType
)


def test_mission_a_knowledge_and_learning():
    async def _run():
        executor = MissionAKnowledgeExecutor()
        res = await executor.execute()
        assert res.passed is True
        assert res.wikilinks_count >= 5
        assert res.lecture_generated is True
        assert res.quiz_score == 100.0
        assert res.transfer_problem_solved is True
        assert "Zero-Knowledge" in res.topic_chosen

    asyncio.run(_run())


def test_mission_b_software_engineering_patch():
    async def _run():
        executor = MissionBSoftwareEngineeringExecutor()
        res = await executor.execute()
        assert res.passed is True
        assert res.patch_applied is True
        assert res.tests_passed is True
        assert res.second_order_tested is True
        assert res.memory_reduced_percent > 70.0

    asyncio.run(_run())


def test_mission_c_9_stage_economic_state_machine():
    async def _run():
        executor = MissionCEconomicExecutor()
        res = await executor.execute()
        assert res.passed is True
        assert len(res.state_transitions) == 9
        # Verify 9 states in sequence
        expected = [
            EconomicState.IDEA,
            EconomicState.HYPOTHESIS,
            EconomicState.MARKET_EVIDENCE,
            EconomicState.LEAD,
            EconomicState.QUALIFIED_LEAD,
            EconomicState.CUSTOMER,
            EconomicState.PAYMENT_ATTEMPT,
            EconomicState.PAYMENT,
            EconomicState.EXTERNAL_VERIFIED_REVENUE
        ]
        assert res.state_transitions == expected
        # Strict Reality Invariants
        assert res.synthetic_revenue_rejected_usd == 1500.00
        assert res.verified_revenue_usd == 299.00
        assert res.pivots_executed == 2
        assert res.computer_use_passed is True

    asyncio.run(_run())


def test_chaos_fault_injection_and_recovery():
    injector = ChaosFaultInjector()
    results = injector.inject_and_recover_faults()
    assert len(results) == 8
    for f_type, ok in results:
        assert ok is True


def test_long_horizon_100_cycles_watchdog():
    async def _run():
        watchdog = LongHorizonWatchdog()
        cycles, ok = await watchdog.execute_100_cycles()
        assert cycles == 100
        assert ok is True

    asyncio.run(_run())


def test_cross_mission_memory_transfer():
    async def _run():
        transfer = CrossMissionMemoryTransfer()
        ok = await transfer.verify_semantic_transfer()
        assert ok is True

    asyncio.run(_run())


def test_extended_autonomous_mission_agent_master():
    async def _run():
        agent = ExtendedAutonomousMissionAgent()
        scorecard, data = await agent.execute_phase8_trial()
        assert scorecard.mission_a_result == "PASS"
        assert scorecard.mission_b_result == "PASS"
        assert scorecard.mission_c_result == "PASS"
        assert scorecard.total_cycles_executed == 100
        assert scorecard.failures_injected == 8
        assert scorecard.recoveries_completed == 8
        assert scorecard.pivots_executed == 2
        assert scorecard.synthetic_as_real_rate == 0.0
        assert scorecard.final_verdict == "EXTENDED_AUTONOMY_PROVEN"

    asyncio.run(_run())
