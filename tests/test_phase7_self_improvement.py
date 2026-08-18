"""
PyTest Test Suite for Phase 7 Autonomous Self-Improvement & Production Trial
"""

import asyncio
import pytest
from agents.self_improvement_agent import (
    SelfImprovementAgent,
    FindingStatus,
    FindingSeverity,
    SelfImprovementFinding,
    PatchPlan,
    MetricDelta
)


def test_codebase_audit_and_prioritization():
    agent = SelfImprovementAgent()
    findings = agent.audit_codebase()
    assert len(findings) == 3
    # Ensure all findings are OBSERVED or REPRODUCED
    for f in findings:
        assert f.status in (FindingStatus.OBSERVED, FindingStatus.REPRODUCED)
        assert f.priority_score > 0.0
    # Ensure sorted by priority descending
    assert findings[0].priority_score >= findings[1].priority_score
    assert findings[1].priority_score >= findings[2].priority_score


def test_patch_plan_generation():
    agent = SelfImprovementAgent()
    findings = agent.audit_codebase()
    for f in findings:
        plan = agent.create_patch_plan(f)
        assert len(plan.files_to_change) > 0
        assert len(plan.functions_to_change) > 0
        assert len(plan.invariants_to_preserve) > 0
        assert len(plan.tests_to_add) > 0


def test_self_improvement_cycle_execution():
    async def _run():
        agent = SelfImprovementAgent()
        findings = agent.audit_codebase()
        
        # Run Cycle 1
        res1 = await agent.execute_patch_cycle(1, findings[0])
        assert res1.success is True
        assert res1.patch_applied is True
        assert res1.patch_reverted is False
        assert len(res1.metrics) > 0
        for m in res1.metrics:
            assert m.improved is True
            assert m.delta != 0.0
        assert res1.second_order_test_passed is True

        # Run Cycle 2
        res2 = await agent.execute_patch_cycle(2, findings[1])
        assert res2.success is True
        assert res2.adr_path is not None

        # Run Cycle 3
        res3 = await agent.execute_patch_cycle(3, findings[2])
        assert res3.success is True

    asyncio.run(_run())


def test_second_order_adversarial_testing():
    agent = SelfImprovementAgent()
    findings = agent.audit_codebase()
    for f in findings:
        passed = agent.execute_second_order_adversarial_test(f)
        assert passed is True


def test_production_trial_mission():
    async def _run():
        agent = SelfImprovementAgent()
        trial = await agent.run_production_trial()
        assert trial.status == "SUCCESS_CONTROLLED_TRIAL"
        assert trial.computer_use_passed is True
        assert len(trial.mvp_files) > 0
        # Strict Reality Invariant
        assert trial.verified_revenue_usd == 0.00

    asyncio.run(_run())


def test_cross_cycle_memory_retention():
    async def _run():
        agent = SelfImprovementAgent()
        findings = agent.audit_codebase()
        await agent.execute_patch_cycle(1, findings[0])
        retained = await agent.verify_memory_across_cycles()
        assert retained is True

    asyncio.run(_run())
