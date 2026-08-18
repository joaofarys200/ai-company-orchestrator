"""
PyTest Test Suite for Phase 6 Controlled Autonomous Real-World Capability Validation
"""

import asyncio
import pytest
from agents.capability_validation_agent import (
    ControlledAutonomousValidationAgent,
    Phase6MemoryEvaluator,
    Phase6LectureEvaluator,
    Phase6EconomicEvaluator,
    Phase6MoneyGenerationEvaluator,
    Phase6ComputerUseEvaluator,
    Phase6FailureInjectionEvaluator,
    Phase6LongHorizonEvaluator,
    Phase6Scorecard,
    ProvenanceClassification,
    EconomicDecision
)


def test_phase6_memory_persistence():
    async def _run():
        evaluator = Phase6MemoryEvaluator()
        results = await evaluator.evaluate_phase6_memory_suite()
        assert len(results) == 15
        for r in results:
            assert r.passed is True
            assert r.score == 100.0

    asyncio.run(_run())


def test_phase6_lecture_cycles():
    async def _run():
        evaluator = Phase6LectureEvaluator()
        results = await evaluator.evaluate_lecture_cycles()
        assert len(results) == 10
        for r in results:
            assert r.passed is True
            assert r.score == 100.0

    asyncio.run(_run())


def test_phase6_economic_discovery_and_pivots():
    async def _run():
        evaluator = Phase6EconomicEvaluator()
        results = await evaluator.evaluate_economic_missions()
        assert len(results) == 4
        # 2 Pivots + 1 Viable Opportunity + 1 Pivot Bounding Gate
        assert "PIVOT 1" in results[0].details
        assert "PIVOT 2" in results[1].details
        assert "BENCHMARK_PASSED" in results[2].details
        assert results[3].passed is True

    asyncio.run(_run())


def test_phase6_money_generation_reality_barrier():
    async def _run():
        evaluator = Phase6MoneyGenerationEvaluator()
        results = await evaluator.evaluate_money_generation_pipeline()
        assert len(results) == 3
        # Stage 1: Pipeline complete
        assert results[0].passed is True
        # Stage 2: Synthetic payment yields 0 verified revenue
        assert results[1].passed is True
        assert "LOCAL_SYNTHETIC" in results[1].details
        assert "verified_revenue_usd = 0.00" in results[1].details
        # Stage 3: External cryptographic payment
        assert results[2].passed is True
        assert "EXTERNAL_VERIFIED" in results[2].details

    asyncio.run(_run())


def test_phase6_computer_use_suite():
    evaluator = Phase6ComputerUseEvaluator()
    results = evaluator.evaluate_computer_use_suite()
    assert len(results) == 5
    for r in results:
        assert r.passed is True


def test_phase6_failure_injections():
    evaluator = Phase6FailureInjectionEvaluator()
    records = evaluator.evaluate_failures()
    assert len(records) == 10
    for f in records:
        assert f.detected is True
        assert f.classified_correctly is True
        assert f.recovered is True
        assert f.verified is True


def test_phase6_long_horizon_50_cycles():
    async def _run():
        evaluator = Phase6LongHorizonEvaluator()
        result = await evaluator.execute_50_cycles()
        assert result.passed is True
        assert result.score == 100.0
        assert "50/50" in result.details

    asyncio.run(_run())


def test_controlled_autonomous_validation_agent_master():
    async def _run():
        agent = ControlledAutonomousValidationAgent()
        scorecard, data = await agent.execute_phase6_full_suite()
        assert scorecard.memory_score == 100.0
        assert scorecard.learning_score == 100.0
        assert scorecard.knowledge_transfer_score == 100.0
        assert scorecard.economic_discovery_score == 100.0
        assert scorecard.economic_decision_score == 100.0
        assert scorecard.money_generation_pipeline_score == 100.0
        assert scorecard.real_evidence_score == 100.0
        assert scorecard.computer_use_score == 100.0
        assert scorecard.recovery_score == 100.0
        assert scorecard.autonomy_score == 100.0
        assert scorecard.synthetic_as_real_rate == 0.0
        assert scorecard.hallucination_rate == 0.0

    asyncio.run(_run())
