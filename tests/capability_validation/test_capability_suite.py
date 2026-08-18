"""
Unit and Integration Tests for Phase 5 Capability Validation Agent
"""

import pytest
import asyncio
from agents.capability_validation_agent import (
    CapabilityValidationAgent,
    MemoryEvaluator,
    LearningEvaluator,
    EconomicEvaluator,
    MoneyGenerationEvaluator,
    EvidenceEvaluator,
    FailureInjectionEvaluator,
    AdversarialEvaluator,
    ProvenanceClassification,
    EconomicDecision,
    FailureClassification
)


def test_memory_evaluator_direct_and_persistence():
    async def _run():
        evaluator = MemoryEvaluator()
        results = await evaluator.evaluate_mem_suite()
        assert len(results) == 15
        for r in results:
            assert r.passed is True
            assert r.factual_accuracy == 100.0

        persist_res = await evaluator.evaluate_memory_persistence()
        assert persist_res.passed is True
        assert persist_res.score == 100.0

    asyncio.run(_run())


def test_learning_evaluator_and_transfer():
    async def _run():
        evaluator = LearningEvaluator()
        lessons = await evaluator.evaluate_lessons()
        assert len(lessons) == 10
        for l in lessons:
            assert l.passed is True
            assert l.student_post_teaching_accuracy == 100.0

        transfer = await evaluator.evaluate_transfer_test()
        assert transfer.passed is True
        assert transfer.score == 100.0
        assert "Idempotency Key" in transfer.details

    asyncio.run(_run())


def test_economic_evaluator_and_pivots():
    async def _run():
        evaluator = EconomicEvaluator()
        results = await evaluator.evaluate_niche_with_autonomous_pivots()
        assert len(results) == 3
        # First 2 are pivots due to negative EV
        assert results[0].decision == EconomicDecision.PIVOT
        assert results[1].decision == EconomicDecision.PIVOT
        # Third is viable
        assert results[2].decision == EconomicDecision.BENCHMARK_PASSED
        assert results[2].margin > 0.0

    asyncio.run(_run())


def test_money_generation_strict_reality_boundary():
    async def _run():
        evaluator = MoneyGenerationEvaluator()
        tests = await evaluator.run_adversarial_economic_suite()
        assert len(tests) == 10
        for t in tests:
            assert t.passed is True

        # Check synthetic events never yield verified revenue
        _, _, rev_synth = evaluator.verify_payment_event('{"amount": 1000}', "hash", is_external=False)
        assert rev_synth == 0.0

        # Check invalid HMAC yields EXTERNAL_UNVERIFIED and 0.0 revenue
        prov_fake, _, rev_fake = evaluator.verify_payment_event('{"amount": 1000}', "wrong_sig", is_external=True)
        assert prov_fake == ProvenanceClassification.EXTERNAL_UNVERIFIED
        assert rev_fake == 0.0

        # Check valid external HMAC yields EXTERNAL_VERIFIED and exact revenue
        payload = '{"amount": 500.0}'
        sig = evaluator.generate_valid_hmac(payload)
        prov_real, dec_real, rev_real = evaluator.verify_payment_event(payload, sig, is_external=True)
        assert prov_real == ProvenanceClassification.EXTERNAL_VERIFIED
        assert dec_real == EconomicDecision.SUCCESS_ECONOMIC
        assert rev_real == 500.0

    asyncio.run(_run())


def test_evidence_evaluator_dom_cases():
    evaluator = EvidenceEvaluator()
    results = evaluator.evaluate_landing_page_cases()
    assert len(results) == 5
    # CASE A-D fail, CASE E passes
    for r in results:
        assert r.passed is True


def test_failure_injection_suite():
    evaluator = FailureInjectionEvaluator()
    records = evaluator.evaluate_failure_injection_suite()
    assert len(records) == 15
    for f in records:
        assert f.detected is True
        assert f.classified_correctly is True
        assert f.recovered is True
        assert f.verified is True


def test_adversarial_evaluator():
    evaluator = AdversarialEvaluator()
    attacks = evaluator.run_adversarial_attacks()
    assert len(attacks) == 5
    for a in attacks:
        assert a.passed is True
        assert a.score == 100.0


def test_full_capability_validation_agent():
    async def _run():
        agent = CapabilityValidationAgent()
        scores, data = await agent.execute_full_validation_suite()
        assert scores.memory_score == 100.0
        assert scores.learning_score == 100.0
        assert scores.economic_score == 100.0
        assert scores.evidence_integrity_score == 100.0
        assert scores.recovery_score == 100.0
        assert scores.autonomy_score == 100.0
        assert scores.synthetic_as_real_rate == 0.0
        assert scores.hallucination_rate == 0.0

    asyncio.run(_run())
