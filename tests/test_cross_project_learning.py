"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Comprehensive Unit & Property Test Suite (20 Mandated Scenarios)
"""

import time
import pytest
from typing import Any, Dict, List

from backend.agents.cross_project_learning.applicability import KnowledgeApplicabilityEngine
from backend.agents.cross_project_learning.bridge import CrossProjectLearningBridge
from backend.agents.cross_project_learning.cache import DeterministicTransferCache
from backend.agents.cross_project_learning.conflicts import ConflictDetector
from backend.agents.cross_project_learning.index import KnowledgeReverseIndex
from backend.agents.cross_project_learning.knowledge import KnowledgeManager
from backend.agents.cross_project_learning.models import (
    ApplicabilityStatus,
    EngineeringKnowledgeItem,
    FeedbackOutcome,
    KnowledgeCategory,
    KnowledgeState,
    ProjectFingerprint,
    TransferDecisionState,
    TransferPolicyName,
)
from backend.agents.cross_project_learning.patterns import PatternLibrary
from backend.agents.cross_project_learning.project_fingerprint import ProjectFingerprintExtractor
from backend.agents.cross_project_learning.security import CrossProjectSecurityFilter
from backend.agents.cross_project_learning.similarity import SimilarityEngine
from backend.agents.cross_project_learning.tests import TestKnowledgeTransferEngine
from backend.agents.cross_project_learning.validator import CrossProjectValidator
from backend.agents.cross_project_learning.verification import VerificationKnowledgeTransferEngine


@pytest.fixture(autouse=True)
def reset_bridge():
    CrossProjectLearningBridge.reset_instance()
    yield
    CrossProjectLearningBridge.reset_instance()


def test_01_fingerprint_determinism():
    """1. Fingerprint determinism: identical structural specs must yield identical SHA256 hashes."""
    fp1 = ProjectFingerprintExtractor.create_fingerprint(
        project_id="proj_alpha",
        languages=["Python", "TypeScript"],
        frameworks=["FastAPI", "React"],
        architecture_style="Modular_Monolith",
    )
    fp2 = ProjectFingerprintExtractor.create_fingerprint(
        project_id="proj_alpha",
        languages=["typescript", "python"],
        frameworks=["react", "fastapi"],
        architecture_style="modular_monolith",
    )
    assert fp1.fingerprint_hash == fp2.fingerprint_hash
    assert len(fp1.fingerprint_hash) == 64


def test_02_knowledge_provenance():
    """2. Knowledge provenance tracks origin project, source file, and transformation history."""
    bridge = CrossProjectLearningBridge.get_instance()
    fp = ProjectFingerprintExtractor.create_fingerprint(project_id="proj_source", languages=["python"])
    bridge.register_fingerprint(fp)

    item = bridge.ingest_knowledge(
        source_project_id="proj_source",
        category=KnowledgeCategory.TEST_PATTERN,
        pattern=PatternLibrary.create_test_pattern("retry_test", "unit", "assert_retry_ok", "fixtures", "status", []),
        context={"languages": ["python"]},
        preconditions=["network_timeout"],
        observed_effect={"resilience": "increased"},
        evidence_scope={"runs": 10},
        source_file="tests/test_retry.py",
    )
    assert item.provenance.source_project_id == "proj_source"
    assert item.provenance.source_file == "tests/test_retry.py"
    assert len(bridge.provenance.get_ledger()) >= 1


def test_03_retrieval_multidimensional():
    """3. Retrieval performs hybrid multidimensional ranking rather than pure keyword matching."""
    bridge = CrossProjectLearningBridge.get_instance()
    fp_src = ProjectFingerprintExtractor.create_fingerprint(project_id="src_p", languages=["python"], frameworks=["fastapi"])
    fp_tgt = ProjectFingerprintExtractor.create_fingerprint(project_id="tgt_p", languages=["python"], frameworks=["fastapi"])
    bridge.register_fingerprint(fp_src)
    bridge.register_fingerprint(fp_tgt)

    item = bridge.ingest_knowledge(
        source_project_id="src_p",
        category=KnowledgeCategory.ARCHITECTURE_PATTERN,
        pattern=PatternLibrary.create_architecture_pattern("hex_arch", "modular_monolith", ["core", "api"], "inward", []),
        context={"languages": ["python"], "frameworks": ["fastapi"], "architecture_style": "modular_monolith"},
        preconditions=[],
        observed_effect={"modularity": "high"},
        evidence_scope={"passed": True},
        auto_validate=True,
        qualify_transferable=True,
    )
    results = bridge.transfer_knowledge(target_project_id="tgt_p", query_intent="completely unrelated keyword phrase")
    assert len(results) >= 1
    decision, cand = results[0]
    assert cand.item.knowledge_id == item.knowledge_id
    assert any("language_overlap" in d for d in cand.matching_dimensions)


def test_04_applicability_with_explanations():
    """4. Applicability engine returns fine-grained status and explicit why/why-not explanations."""
    fp_tgt = ProjectFingerprintExtractor.create_fingerprint(
        project_id="tgt_app",
        languages=["typescript"],
        frameworks=["react"],
        architecture_style="modular_monolith",
    )
    cand_item = EngineeringKnowledgeItem(
        knowledge_id="k_test_app",
        source_project_id="p1",
        source_project_fingerprint="hash1",
        category=KnowledgeCategory.TEST_PATTERN,
        pattern=PatternLibrary.create_test_pattern("p_test", "unit", "inv1", "fix", "assert", []),
        context={"languages": ["python"], "architecture_style": "modular_monolith"},
        preconditions=["browser_automation"],
        observed_effect={},
        evidence_scope={},
        confidence=0.8,
        provenance=None,  # type: ignore
        state=KnowledgeState.TRANSFERABLE,
    )
    from backend.agents.cross_project_learning.models import CandidateKnowledge
    cand = CandidateKnowledge(
        item=cand_item,
        score=0.7,
        matching_dimensions=["architecture_match"],
        missing_dimensions=["language_mismatch"],
        contradictions=[],
        provenance=None,  # type: ignore
        applicability_confidence=0.6,
    )
    result = KnowledgeApplicabilityEngine.evaluate_applicability(cand, fp_tgt)
    assert len(result.why_applicable) > 0 or len(result.why_not_applicable) > 0
    assert result.status in (ApplicabilityStatus.CONTEXT_REQUIRED, ApplicabilityStatus.PARTIALLY_APPLICABLE)


def test_05_incompatible_architecture():
    """5. Incompatible architecture and language produces INCOMPATIBLE status and transfer rejection."""
    fp_tgt = ProjectFingerprintExtractor.create_fingerprint(
        project_id="tgt_incomp",
        languages=["csharp"],
        architecture_style="event_driven_microservices",
    )
    cand_item = EngineeringKnowledgeItem(
        knowledge_id="k_incomp",
        source_project_id="p_src",
        source_project_fingerprint="hash_src",
        category=KnowledgeCategory.ARCHITECTURE_PATTERN,
        pattern=PatternLibrary.create_architecture_pattern("monolith_pattern", "monolith", [], "", []),
        context={"languages": ["python"], "architecture_style": "monolith"},
        preconditions=["sqlite", "browser_automation"],
        observed_effect={},
        evidence_scope={},
        confidence=0.5,
        provenance=None,  # type: ignore
        state=KnowledgeState.TRANSFERABLE,
    )
    from backend.agents.cross_project_learning.models import CandidateKnowledge
    cand = CandidateKnowledge(
        item=cand_item,
        score=0.1,
        matching_dimensions=[],
        missing_dimensions=["language_mismatch", "architecture_drift"],
        contradictions=[],
        provenance=None,  # type: ignore
        applicability_confidence=0.2,
    )
    res = KnowledgeApplicabilityEngine.evaluate_applicability(cand, fp_tgt)
    assert res.status == ApplicabilityStatus.INCOMPATIBLE
    from backend.agents.cross_project_learning.transfer import TransferGovernanceEngine
    dec = TransferGovernanceEngine.decide_transfer(cand, res, fp_tgt)
    assert dec.state == TransferDecisionState.REJECT_TRANSFER


def test_06_cross_language_hypothesis():
    """6. Cross-language transfer produces TRANSFER_AS_HYPOTHESIS with adapter requirement."""
    fp_tgt = ProjectFingerprintExtractor.create_fingerprint(
        project_id="tgt_ts",
        languages=["typescript"],
        frameworks=["react"],
    )
    cand_item = EngineeringKnowledgeItem(
        knowledge_id="k_retry_py",
        source_project_id="p_py",
        source_project_fingerprint="hash_py",
        category=KnowledgeCategory.TEST_PATTERN,
        pattern=PatternLibrary.create_test_pattern("retry_pattern", "unit", "exponential_retry", "", "", []),
        context={"languages": ["python"]},
        preconditions=[],
        observed_effect={},
        evidence_scope={},
        confidence=0.9,
        provenance=None,  # type: ignore
        state=KnowledgeState.TRANSFERABLE,
    )
    from backend.agents.cross_project_learning.models import CandidateKnowledge
    cand = CandidateKnowledge(
        item=cand_item,
        score=0.75,
        matching_dimensions=[],
        missing_dimensions=["language_mismatch"],
        contradictions=[],
        provenance=None,  # type: ignore
        applicability_confidence=0.75,
    )
    app = KnowledgeApplicabilityEngine.evaluate_applicability(cand, fp_tgt)
    assert app.adapter_needed is True
    from backend.agents.cross_project_learning.transfer import TransferGovernanceEngine
    dec = TransferGovernanceEngine.decide_transfer(cand, app, fp_tgt)
    assert dec.state in (TransferDecisionState.TRANSFER_AS_HYPOTHESIS, TransferDecisionState.TRANSFER_TO_TEST_GENERATION)
    assert dec.local_validation_plan.get("required_local_validation") is True


def test_07_conflict_detection_prevents_merge():
    """7. Opposing architecture patterns in same domain are marked CONFLICTED without merging."""
    km = KnowledgeManager()
    item_a = km.create_observed_item(
        source_project_id="p_a",
        source_project_fingerprint="h_a",
        category=KnowledgeCategory.ARCHITECTURE_PATTERN,
        pattern={"architecture_style": "monolith"},
        context={"domain": "billing"},
        preconditions=[],
        observed_effect={},
        evidence_scope={},
        confidence=0.8,
    )
    item_b = km.create_observed_item(
        source_project_id="p_b",
        source_project_fingerprint="h_b",
        category=KnowledgeCategory.ARCHITECTURE_PATTERN,
        pattern={"architecture_style": "microservice"},
        context={"domain": "billing"},
        preconditions=[],
        observed_effect={},
        evidence_scope={},
        confidence=0.8,
    )
    detector = ConflictDetector()
    conflict = detector.check_conflict(item_a, item_b)
    assert conflict is not None
    assert conflict.conflict_type == "ARCHITECTURAL_CONTRADICTION"
    assert item_a.state == KnowledgeState.CONFLICTED
    assert item_b.state == KnowledgeState.CONFLICTED


def test_08_staleness_management():
    """8. Stale items are flagged without erasing historical records."""
    km = KnowledgeManager()
    item = km.create_observed_item(
        source_project_id="p1",
        source_project_fingerprint="h1",
        category=KnowledgeCategory.CONTRACT_PATTERN,
        pattern={"protocol": "http_rest"},
        context={},
        preconditions=[],
        observed_effect={},
        evidence_scope={},
        confidence=0.9,
    )
    km.mark_stale(item.knowledge_id, reason="Framework upgraded to v2.0 breaking legacy schema")
    assert item.state == KnowledgeState.STALE
    assert "Framework upgraded" in item.context["staleness_reason"]


def test_09_transfer_rejection_governance():
    """9. Transfer governance rejects transfer when applicability status is INCOMPATIBLE."""
    fp = ProjectFingerprintExtractor.create_fingerprint(project_id="p_test")
    item = EngineeringKnowledgeItem(
        knowledge_id="k1",
        source_project_id="p_src",
        source_project_fingerprint="h_src",
        category=KnowledgeCategory.BROWSER_PATTERN,
        pattern={},
        context={},
        preconditions=[],
        observed_effect={},
        evidence_scope={},
        confidence=0.2,
        provenance=None,  # type: ignore
        state=KnowledgeState.TRANSFERABLE,
    )
    from backend.agents.cross_project_learning.models import CandidateKnowledge, ApplicabilityResult
    cand = CandidateKnowledge(item=item, score=0.1, matching_dimensions=[], missing_dimensions=[], contradictions=[], provenance=None, applicability_confidence=0.1)  # type: ignore
    app = ApplicabilityResult(status=ApplicabilityStatus.INCOMPATIBLE, confidence=0.1, why_not_applicable=["Missing UI"])
    from backend.agents.cross_project_learning.transfer import TransferGovernanceEngine
    dec = TransferGovernanceEngine.decide_transfer(cand, app, fp)
    assert dec.state == TransferDecisionState.REJECT_TRANSFER


def test_10_local_validation_produces_local_evidence():
    """10. Local validation creates local proof receipts and updates confidence."""
    bridge = CrossProjectLearningBridge.get_instance()
    fp_tgt = ProjectFingerprintExtractor.create_fingerprint(project_id="tgt_val", languages=["python"])
    bridge.register_fingerprint(fp_tgt)

    item = bridge.ingest_knowledge(
        source_project_id="tgt_val",
        category=KnowledgeCategory.TEST_PATTERN,
        pattern={"target_invariant": "assert x > 0"},
        context={"languages": ["python"]},
        preconditions=[],
        observed_effect={},
        evidence_scope={"runs": 1},
        auto_validate=True,
        qualify_transferable=True,
    )
    decisions = bridge.transfer_knowledge(target_project_id="tgt_val")
    assert len(decisions) >= 1
    dec, _ = decisions[0]

    val_res = bridge.execute_local_validation(dec, should_fail=False)
    assert val_res.validated is True
    assert val_res.outcome == FeedbackOutcome.TRANSFER_SUCCESS
    assert "exit_code" in val_res.evidence


def test_11_transfer_harm_detection_and_penalty():
    """11. Harm detection captures negative impact, penalizes confidence, and registers telemetry."""
    bridge = CrossProjectLearningBridge.get_instance()
    fp = ProjectFingerprintExtractor.create_fingerprint(project_id="tgt_harm", languages=["python"])
    bridge.register_fingerprint(fp)

    item = bridge.ingest_knowledge(
        source_project_id="tgt_harm",
        category=KnowledgeCategory.TEST_PATTERN,
        pattern={"target_invariant": "assert unstable == True"},
        context={"languages": ["python"]},
        preconditions=[],
        observed_effect={},
        evidence_scope={"runs": 1},
        confidence=0.85,
        auto_validate=True,
        qualify_transferable=True,
    )
    decisions = bridge.transfer_knowledge(target_project_id="tgt_harm")
    dec, _ = decisions[0]

    val_res = bridge.execute_local_validation(dec, induces_harm=True)
    assert val_res.harm_detected is True
    assert val_res.outcome == FeedbackOutcome.TRANSFER_HARM

    # Check updated confidence in knowledge manager
    updated_item = bridge.km.get_item(item.knowledge_id)
    assert updated_item is not None
    assert updated_item.confidence <= 0.65
    assert updated_item.harm_count == 1


def test_12_feedback_loop_updates():
    """12. Successful validation increments success count and confidence bonus."""
    km = KnowledgeManager()
    item = km.create_observed_item("p1", "h1", KnowledgeCategory.REPAIR_PATTERN, {}, {}, [], {}, {}, 0.70)
    km.promote_to_validated(item.knowledge_id, {})
    km.qualify_for_transfer(item.knowledge_id, min_confidence=0.60)

    km.register_feedback(item.knowledge_id, is_success=True, is_harm=False, bonus=0.08)
    assert item.success_count == 1
    assert item.confidence == pytest.approx(0.78, abs=1e-3)


def test_13_security_sentinel_filtering():
    """13. Security sentinel strictly blocks ingestion of destructive shell or credentials."""
    bridge = CrossProjectLearningBridge.get_instance()
    fp = ProjectFingerprintExtractor.create_fingerprint(project_id="p_sec")
    bridge.register_fingerprint(fp)

    # Destructive code attempt
    with pytest.raises(PermissionError) as exc_info:
        bridge.ingest_knowledge(
            source_project_id="p_sec",
            category=KnowledgeCategory.REPAIR_PATTERN,
            pattern={"cmd": "rm -rf /"},
            context={},
            preconditions=[],
            observed_effect={},
            evidence_scope={},
        )
    assert "SECURITY_QUARANTINE_TRIGGERED" in str(exc_info.value)

    # Secret exfiltration attempt
    with pytest.raises(PermissionError) as exc_info2:
        bridge.ingest_knowledge(
            source_project_id="p_sec",
            category=KnowledgeCategory.CONTRACT_PATTERN,
            pattern={"api_key": "api_key = 'abcdef1234567890abcdef'"},
            context={},
            preconditions=[],
            observed_effect={},
            evidence_scope={},
        )
    assert "SECURITY_QUARANTINE_TRIGGERED" in str(exc_info2.value)


def test_14_cache_invalidation_and_evidence_isolation():
    """14. Cache returns cached decisions but does not invent fresh verification evidence."""
    cache = DeterministicTransferCache()
    key = cache.compute_cache_key("k1", "tgt_fp", "STANDARD")

    from backend.agents.cross_project_learning.models import KnowledgeTransferDecision
    dec = KnowledgeTransferDecision(
        decision_id="dec_c1",
        state=TransferDecisionState.TRANSFER_AS_HYPOTHESIS,
        target_project_id="tgt_p",
        item_id="k1",
        category=KnowledgeCategory.TEST_PATTERN,
        rationale="Cached rationale",
    )
    cache.put(key, dec, target_fingerprint_hash="tgt_fp")
    retrieved = cache.get(key)
    assert retrieved is not None
    assert "[FROM_DETERMINISTIC_CACHE]" in retrieved.rationale

    # Invalidate cache
    invalidated_count = cache.invalidate("tgt_fp")
    assert invalidated_count == 1
    assert cache.get(key) is None


def test_15_evidence_isolation_invariant():
    """15. Central Invariant: External knowledge cannot mark local target as VERIFIED."""
    hints = VerificationKnowledgeTransferEngine.generate_verification_hints(
        knowledge_item=EngineeringKnowledgeItem(
            knowledge_id="k_ext",
            source_project_id="ext_proj",
            source_project_fingerprint="ext_hash",
            category=KnowledgeCategory.TEST_PATTERN,
            pattern={"target_invariant": "assert True"},
            context={},
            preconditions=[],
            observed_effect={},
            evidence_scope={},
            confidence=0.99,
            provenance=None,  # type: ignore
        ),
        target_fingerprint=ProjectFingerprintExtractor.create_fingerprint(project_id="local_proj"),
    )
    assert hints["cannot_grant_verification"] is True
    assert hints["verification_rule"] == "ADVISORY_HINT_ONLY_LOCAL_EVIDENCE_MANDATORY"


def test_16_false_transfer_prevention():
    """16. Invariant: OBSERVED knowledge can NEVER be promoted to TRANSFERABLE directly."""
    km = KnowledgeManager()
    item = km.create_observed_item("p1", "h1", KnowledgeCategory.TEST_PATTERN, {}, {}, [], {}, {}, 0.90)
    assert item.state == KnowledgeState.OBSERVED

    with pytest.raises(PermissionError) as exc_info:
        km.qualify_for_transfer(item.knowledge_id)
    assert "Invariant Violation" in str(exc_info.value)


def test_17_human_review_policy_trigger():
    """17. STRICT and SECURITY_FIRST policies mandate human review on uncertain transfers."""
    fp = ProjectFingerprintExtractor.create_fingerprint(project_id="p_strict", languages=["typescript"])
    cand_item = EngineeringKnowledgeItem(
        knowledge_id="k_strict",
        source_project_id="p_py",
        source_project_fingerprint="h_py",
        category=KnowledgeCategory.CONTRACT_PATTERN,
        pattern={},
        context={"languages": ["python"]},
        preconditions=[],
        observed_effect={},
        evidence_scope={},
        confidence=0.65,
        provenance=None,  # type: ignore
        state=KnowledgeState.TRANSFERABLE,
    )
    from backend.agents.cross_project_learning.models import CandidateKnowledge, ApplicabilityResult
    cand = CandidateKnowledge(item=cand_item, score=0.65, matching_dimensions=[], missing_dimensions=[], contradictions=[], provenance=None, applicability_confidence=0.65)  # type: ignore
    app = ApplicabilityResult(status=ApplicabilityStatus.CONTEXT_REQUIRED, confidence=0.65, adapter_needed=True, target_language="typescript")
    from backend.agents.cross_project_learning.transfer import TransferGovernanceEngine
    dec = TransferGovernanceEngine.decide_transfer(cand, app, fp, policy=TransferPolicyName.STRICT)
    assert dec.state == TransferDecisionState.HUMAN_REVIEW
    assert dec.requires_human_review is True


def test_18_large_knowledge_reverse_index():
    """18. KnowledgeReverseIndex provides O(1) key indexing and rapid intersection queries."""
    index = KnowledgeReverseIndex()
    for i in range(100):
        item = EngineeringKnowledgeItem(
            knowledge_id=f"k_idx_{i}",
            source_project_id=f"p_{i % 5}",
            source_project_fingerprint="h",
            category=KnowledgeCategory.TEST_PATTERN,
            pattern={"risk_class": "concurrency" if i % 2 == 0 else "network_timeout"},
            context={"languages": ["python" if i % 3 == 0 else "typescript"], "architecture_style": "modular_monolith"},
            preconditions=[],
            observed_effect={},
            evidence_scope={},
            confidence=0.8,
            provenance=None,  # type: ignore
        )
        index.index_item(item)

    assert index.size() == 100
    res = index.query_by_keys(language="python", architecture="modular_monolith", risk="concurrency")
    assert len(res) > 0
    assert all("python" in x.context["languages"] for x in res)


def test_19_unseen_project_evaluation():
    """19. Unseen project fingerprint correctly processed producing valid transfer and local plan."""
    bridge = CrossProjectLearningBridge.get_instance()
    fp_unseen = ProjectFingerprintExtractor.create_fingerprint(
        project_id="unseen_iot_gateway",
        languages=["python"],
        frameworks=["fastapi"],
        communication_mechanisms=["websocket", "http_rest"],
        risk_classes=["network_timeout"],
    )
    bridge.register_fingerprint(fp_unseen)

    bridge.ingest_knowledge(
        source_project_id="prior_mesh",
        category=KnowledgeCategory.REPAIR_PATTERN,
        pattern=PatternLibrary.create_repair_pattern("ws_reconnect", "timeout_disconnect", "exp_backoff", ["ping_check"]),
        context={"languages": ["python"], "communication_mechanisms": ["websocket"]},
        preconditions=["websocket"],
        observed_effect={"stability": "improved"},
        evidence_scope={"runs": 5},
        auto_validate=True,
        qualify_transferable=True,
    )
    decisions = bridge.transfer_knowledge(target_project_id="unseen_iot_gateway")
    assert len(decisions) >= 1
    dec, _ = decisions[0]
    assert dec.target_project_id == "unseen_iot_gateway"
    assert dec.local_validation_plan["required_local_validation"] is True


def test_20_ablation_invariants():
    """20. Ablation invariant: Applicability filtering prevents transferring incompatible items."""
    fp_tgt = ProjectFingerprintExtractor.create_fingerprint(project_id="tgt_ablation", languages=["python"])
    item_incomp = EngineeringKnowledgeItem(
        knowledge_id="k_ablation_incomp",
        source_project_id="src_other",
        source_project_fingerprint="h_other",
        category=KnowledgeCategory.BROWSER_PATTERN,
        pattern={},
        context={"languages": ["swift"]},
        preconditions=["ios_simulator"],
        observed_effect={},
        evidence_scope={},
        confidence=0.3,
        provenance=None,  # type: ignore
        state=KnowledgeState.TRANSFERABLE,
    )
    from backend.agents.cross_project_learning.models import CandidateKnowledge
    cand = CandidateKnowledge(item=item_incomp, score=0.2, matching_dimensions=[], missing_dimensions=["language_mismatch"], contradictions=[], provenance=None, applicability_confidence=0.2)  # type: ignore

    # Mode B (Naive retrieval only): Would blindly accept cand based on any similarity
    naive_accept = cand.score > 0.0

    # Mode C (Applicability filtered): Evaluates structural compatibility
    app = KnowledgeApplicabilityEngine.evaluate_applicability(cand, fp_tgt)
    filtered_accept = app.status != ApplicabilityStatus.INCOMPATIBLE

    assert naive_accept is True
    assert filtered_accept is False  # Mode C correctly prevents false transfer


import unittest

class CrossProjectLearningTestCase(unittest.TestCase):
    def setUp(self):
        CrossProjectLearningBridge.reset_instance()

    def tearDown(self):
        CrossProjectLearningBridge.reset_instance()

    def test_01(self): test_01_fingerprint_determinism()
    def test_02(self): test_02_knowledge_provenance()
    def test_03(self): test_03_retrieval_multidimensional()
    def test_04(self): test_04_applicability_with_explanations()
    def test_05(self): test_05_incompatible_architecture()
    def test_06(self): test_06_cross_language_hypothesis()
    def test_07(self): test_07_conflict_detection_prevents_merge()
    def test_08(self): test_08_staleness_management()
    def test_09(self): test_09_transfer_rejection_governance()
    def test_10(self): test_10_local_validation_produces_local_evidence()
    def test_11(self): test_11_transfer_harm_detection_and_penalty()
    def test_12(self): test_12_feedback_loop_updates()
    def test_13(self): test_13_security_sentinel_filtering()
    def test_14(self): test_14_cache_invalidation_and_evidence_isolation()
    def test_15(self): test_15_evidence_isolation_invariant()
    def test_16(self): test_16_false_transfer_prevention()
    def test_17(self): test_17_human_review_policy_trigger()
    def test_18(self): test_18_large_knowledge_reverse_index()
    def test_19(self): test_19_unseen_project_evaluation()
    def test_20(self): test_20_ablation_invariants()

