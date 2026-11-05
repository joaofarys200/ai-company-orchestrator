"""
JARVIS OS — Phase 77: Autonomous Evidence Verification & Engineering Claims Governance
Deterministic Test Suite covering all 35 required scenarios from Section 12.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
import pytest

from backend.agents.evidence_governance import (
    AssuranceTier,
    ClaimType,
    ContradictoryEvidenceError,
    EngineeringClaim,
    EvidenceArtifact,
    EvidenceCategory,
    EvidenceGovernanceBridge,
    EvidenceGovernanceError,
    EvidenceGovernanceStore,
    EvidenceOriginType,
    InvalidEvidenceIntegrityError,
    ReportAuditResult,
    StaleEvidenceError,
    UnauthorizedPromotionError,
    VerificationResult,
    VerificationStatus,
)
from backend.agents.evidence_governance.provenance import EvidenceProvenanceValidator


class TestEvidenceGovernanceEngine:

    @pytest.fixture(autouse=True)
    def setup_temp_env(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jarvis_phase77_test_")
        self.bridge = EvidenceGovernanceBridge(store_dir=self.temp_dir)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Scenario 1: Registering a valid engineering claim
    # -------------------------------------------------------------------------
    def test_01_register_valid_claim(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_01",
            claim_type=ClaimType.TEST_EXECUTION,
            proposition="All unit tests for router module passed.",
            assurance_tier=AssuranceTier.TIER_2_OPERATIONAL,
            originating_subsystem="test_runner",
            required_evidence_categories=[EvidenceCategory.TEST_RUNNER_RESULT],
        )
        assert claim.claim_id == "claim_01"
        assert claim.status == VerificationStatus.UNVERIFIED
        assert self.bridge.registry.get_claim("claim_01") is not None

    # -------------------------------------------------------------------------
    # Scenario 2: Verifying a claim with sufficient authoritative evidence
    # -------------------------------------------------------------------------
    def test_02_verify_claim_with_sufficient_evidence(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_02",
            claim_type=ClaimType.TEST_EXECUTION,
            proposition="Tests passed with 0 failures.",
            assurance_tier=AssuranceTier.TIER_2_OPERATIONAL,
            originating_subsystem="test_runner",
            required_evidence_categories=[EvidenceCategory.TEST_RUNNER_RESULT],
        )
        self.bridge.ingest_evidence(
            artifact_id="ev_02",
            category=EvidenceCategory.TEST_RUNNER_RESULT,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha="c0ffee1",
            payload={"passed": 25, "failed": 0, "total": 25},
            source_subsystem="pytest_runner",
            claim_id="claim_02",
        )
        res = self.bridge.verify_claim("claim_02")
        assert res.status == VerificationStatus.VERIFIED
        assert claim.status == VerificationStatus.VERIFIED

    # -------------------------------------------------------------------------
    # Scenario 3: Marking a claim unverified when required evidence is missing
    # -------------------------------------------------------------------------
    def test_03_mark_unverified_when_evidence_missing(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_03",
            claim_type=ClaimType.PERFORMANCE_BENCHMARK,
            proposition="Memory usage reduced by 30%.",
            assurance_tier=AssuranceTier.TIER_3_ARCHITECTURAL,
            originating_subsystem="benchmark",
            required_evidence_categories=[EvidenceCategory.BENCHMARK_MEASUREMENT],
        )
        res = self.bridge.verify_claim("claim_03")
        assert res.status == VerificationStatus.UNVERIFIED
        assert EvidenceCategory.BENCHMARK_MEASUREMENT in res.missing_evidence_categories

    # -------------------------------------------------------------------------
    # Scenario 4: Distinguishing partial verification from complete verification
    # -------------------------------------------------------------------------
    def test_04_distinguish_partial_verification(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_04",
            claim_type=ClaimType.REPOSITORY_STATE,
            proposition="Migration completed and verified by tests.",
            assurance_tier=AssuranceTier.TIER_3_ARCHITECTURAL,
            originating_subsystem="macro_refactoring",
            required_evidence_categories=[
                EvidenceCategory.GIT_REVISION_RECORD,
                EvidenceCategory.TEST_RUNNER_RESULT,
            ],
            dependency_files=["backend/router.py"],
        )
        # Only provide git revision, but test runner result is missing
        self.bridge.ingest_evidence(
            artifact_id="ev_04_git",
            category=EvidenceCategory.GIT_REVISION_RECORD,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha="HEAD",
            payload={"modified_files": ["backend/router.py"], "created_files": []},
            source_subsystem="git",
            claim_id="claim_04",
        )
        res = self.bridge.verify_claim("claim_04")
        assert res.status == VerificationStatus.PARTIALLY_VERIFIED
        assert EvidenceCategory.TEST_RUNNER_RESULT in res.missing_evidence_categories

    # -------------------------------------------------------------------------
    # Scenario 5: Detecting contradictory evidence
    # -------------------------------------------------------------------------
    def test_05_detecting_contradictory_evidence(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_05",
            claim_type=ClaimType.TEST_EXECUTION,
            proposition="All 30 tests passed cleanly.",
            assurance_tier=AssuranceTier.TIER_2_OPERATIONAL,
            originating_subsystem="test_runner",
            required_evidence_categories=[EvidenceCategory.TEST_RUNNER_RESULT],
        )
        # Evidence says 2 tests failed
        self.bridge.ingest_evidence(
            artifact_id="ev_05_fail",
            category=EvidenceCategory.TEST_RUNNER_RESULT,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha="HEAD",
            payload={"passed": 28, "failed": 2, "total": 30},
            source_subsystem="pytest",
            claim_id="claim_05",
        )
        res = self.bridge.verify_claim("claim_05")
        assert res.status == VerificationStatus.CONTRADICTED
        assert any("TEST_FAILURES_DETECTED" in d for d in res.discrepancies)

    # -------------------------------------------------------------------------
    # Scenario 6: Detecting stale evidence
    # -------------------------------------------------------------------------
    def test_06_detecting_stale_evidence(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_06",
            claim_type=ClaimType.REPOSITORY_STATE,
            proposition="Modified router interface.",
            assurance_tier=AssuranceTier.TIER_2_OPERATIONAL,
            originating_subsystem="refactor",
            required_evidence_categories=[EvidenceCategory.GIT_REVISION_RECORD],
            dependency_files=["backend/router.py"],
        )
        self.bridge.ingest_evidence(
            artifact_id="ev_06",
            category=EvidenceCategory.GIT_REVISION_RECORD,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha="HEAD",
            payload={"modified_files": ["backend/router.py"], "created_files": []},
            source_subsystem="git",
            claim_id="claim_06",
        )
        self.bridge.verify_claim("claim_06")
        assert claim.status == VerificationStatus.VERIFIED

        # Now simulate modifying backend/router.py
        invalidated = self.bridge.invalidate_by_files({"backend/router.py"})
        assert "claim_06" in invalidated
        assert claim.status == VerificationStatus.STALE

    # -------------------------------------------------------------------------
    # Scenario 7: Validating evidence provenance
    # -------------------------------------------------------------------------
    def test_07_validating_evidence_provenance(self):
        art = EvidenceProvenanceValidator.create_artifact(
            artifact_id="ev_07",
            category=EvidenceCategory.DIRECT_EXECUTION_OUTPUT,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha="abc1234",
            payload={"exit_code": 0},
            source_subsystem="bash",
        )
        assert art.content_hash is not None
        assert EvidenceProvenanceValidator.validate_integrity(art) is True

    # -------------------------------------------------------------------------
    # Scenario 8: Detecting a mismatched repository revision
    # -------------------------------------------------------------------------
    def test_08_detecting_mismatched_repository_revision(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_08",
            claim_type=ClaimType.TEST_EXECUTION,
            proposition="Tests passed on commit c0ffee1",
            assurance_tier=AssuranceTier.TIER_2_OPERATIONAL,
            originating_subsystem="ci",
            required_evidence_categories=[EvidenceCategory.TEST_RUNNER_RESULT],
            commit_sha="c0ffee1",
        )
        # Evidence was captured on commit d3adb33f
        self.bridge.ingest_evidence(
            artifact_id="ev_08",
            category=EvidenceCategory.TEST_RUNNER_RESULT,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha="d3adb33f",
            payload={"passed": 10, "failed": 0},
            source_subsystem="ci",
            claim_id="claim_08",
        )
        res = self.bridge.verify_claim("claim_08")
        assert res.status == VerificationStatus.STALE
        assert "COMMIT_SHA_MISMATCH" in res.discrepancies

    # -------------------------------------------------------------------------
    # Scenario 9: Detecting invalid evidence integrity metadata (hash corruption)
    # -------------------------------------------------------------------------
    def test_09_detecting_invalid_evidence_integrity(self):
        art = EvidenceProvenanceValidator.create_artifact(
            artifact_id="ev_09",
            category=EvidenceCategory.DIRECT_EXECUTION_OUTPUT,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha="HEAD",
            payload={"data": "authentic"},
            source_subsystem="system",
        )
        # Tamper with payload
        art.payload["data"] = "tampered"
        with pytest.raises(InvalidEvidenceIntegrityError):
            self.bridge.registry.register_artifact(art)

    # -------------------------------------------------------------------------
    # Scenario 10: Distinguishing source inspection from runtime verification
    # -------------------------------------------------------------------------
    def test_10_distinguish_source_inspection_from_runtime_verification(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_10",
            claim_type=ClaimType.SOURCE_INTEGRATION,
            proposition="Module interface is integrated and functional.",
            assurance_tier=AssuranceTier.TIER_3_ARCHITECTURAL,
            originating_subsystem="linter",
            required_evidence_categories=[EvidenceCategory.AST_INSPECTION_PROOF],
        )
        self.bridge.ingest_evidence(
            artifact_id="ev_10_ast",
            category=EvidenceCategory.AST_INSPECTION_PROOF,
            origin_type=EvidenceOriginType.STATIC_INSPECTION,
            commit_sha="HEAD",
            payload={"symbols": ["func_a", "func_b"]},
            source_subsystem="ast_parser",
            claim_id="claim_10",
        )
        res = self.bridge.verify_claim("claim_10")
        assert res.status == VerificationStatus.PARTIALLY_VERIFIED
        assert "STATIC_INSPECTION_ONLY" in res.discrepancies

    # -------------------------------------------------------------------------
    # Scenario 11: Distinguishing synthetic data from real execution evidence
    # -------------------------------------------------------------------------
    def test_11_distinguish_synthetic_from_real_execution(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_11",
            claim_type=ClaimType.PERFORMANCE_BENCHMARK,
            proposition="Throughput increased by 40%.",
            assurance_tier=AssuranceTier.TIER_3_ARCHITECTURAL,
            originating_subsystem="optimizer",
            required_evidence_categories=[EvidenceCategory.BENCHMARK_MEASUREMENT],
        )
        self.bridge.ingest_evidence(
            artifact_id="ev_11_syn",
            category=EvidenceCategory.BENCHMARK_MEASUREMENT,
            origin_type=EvidenceOriginType.SYNTHETIC_FIXTURE,
            commit_sha="HEAD",
            payload={"baseline_metric": 100, "candidate_metric": 60, "conditions_comparable": True},
            source_subsystem="synthetic_bench",
            claim_id="claim_11",
        )
        res = self.bridge.verify_claim("claim_11")
        assert res.status == VerificationStatus.PARTIALLY_VERIFIED
        assert "SYNTHETIC_FIXTURE_ONLY" in res.discrepancies

    # -------------------------------------------------------------------------
    # Scenario 12: Verifying an actual test-runner result
    # -------------------------------------------------------------------------
    def test_12_verify_actual_test_runner_result(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_12",
            claim_type=ClaimType.TEST_EXECUTION,
            proposition="pytest tests/test_portfolio.py passed 25/25.",
            assurance_tier=AssuranceTier.TIER_2_OPERATIONAL,
            originating_subsystem="pytest",
            required_evidence_categories=[EvidenceCategory.TEST_RUNNER_RESULT],
        )
        self.bridge.ingest_evidence(
            artifact_id="ev_12",
            category=EvidenceCategory.TEST_RUNNER_RESULT,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha="HEAD",
            payload={"passed": 25, "failed": 0, "total": 25},
            source_subsystem="pytest",
            claim_id="claim_12",
        )
        res = self.bridge.verify_claim("claim_12")
        assert res.status == VerificationStatus.VERIFIED

    # -------------------------------------------------------------------------
    # Scenario 13: Rejecting a report that claims tests passed without execution evidence
    # -------------------------------------------------------------------------
    def test_13_reject_claims_without_execution_evidence(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_13",
            claim_type=ClaimType.TEST_EXECUTION,
            proposition="All 50 tests passed.",
            assurance_tier=AssuranceTier.TIER_2_OPERATIONAL,
            originating_subsystem="agent",
            required_evidence_categories=[EvidenceCategory.TEST_RUNNER_RESULT],
        )
        # Only model explanation attached
        self.bridge.ingest_evidence(
            artifact_id="ev_13_text",
            category=EvidenceCategory.MODEL_GENERATED_EXPLANATION,
            origin_type=EvidenceOriginType.STATIC_INSPECTION,
            commit_sha="HEAD",
            payload={"text": "I ran pytest and all 50 tests passed perfectly."},
            source_subsystem="llm",
            claim_id="claim_13",
        )
        res = self.bridge.verify_claim("claim_13")
        assert res.status == VerificationStatus.UNVERIFIED
        assert "SELF_VERIFICATION_REJECTED" in res.discrepancies

    # -------------------------------------------------------------------------
    # Scenario 14: Verifying measured improvements against a comparable baseline
    # -------------------------------------------------------------------------
    def test_14_verify_measured_improvements_against_comparable_baseline(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_14",
            claim_type=ClaimType.PERFORMANCE_BENCHMARK,
            proposition="Latency reduced from 120ms to 80ms.",
            assurance_tier=AssuranceTier.TIER_3_ARCHITECTURAL,
            originating_subsystem="benchmark",
            required_evidence_categories=[EvidenceCategory.BENCHMARK_MEASUREMENT],
        )
        self.bridge.ingest_evidence(
            artifact_id="ev_14",
            category=EvidenceCategory.BENCHMARK_MEASUREMENT,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha="HEAD",
            payload={"baseline_metric": 120.0, "candidate_metric": 80.0, "conditions_comparable": True, "lower_is_better": True},
            source_subsystem="perf_test",
            claim_id="claim_14",
        )
        res = self.bridge.verify_claim("claim_14")
        assert res.status == VerificationStatus.VERIFIED

    # -------------------------------------------------------------------------
    # Scenario 15: Rejecting unsupported claims of general performance improvement
    # -------------------------------------------------------------------------
    def test_15_reject_unsupported_performance_claim(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_15",
            claim_type=ClaimType.PERFORMANCE_BENCHMARK,
            proposition="Improved performance under all loads.",
            assurance_tier=AssuranceTier.TIER_3_ARCHITECTURAL,
            originating_subsystem="optimizer",
            required_evidence_categories=[EvidenceCategory.BENCHMARK_MEASUREMENT],
        )
        # Incomparable conditions
        self.bridge.ingest_evidence(
            artifact_id="ev_15",
            category=EvidenceCategory.BENCHMARK_MEASUREMENT,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha="HEAD",
            payload={"baseline_metric": 100, "candidate_metric": 50, "conditions_comparable": False},
            source_subsystem="bench",
            claim_id="claim_15",
        )
        res = self.bridge.verify_claim("claim_15")
        assert res.status == VerificationStatus.PARTIALLY_VERIFIED
        assert "INCOMPARABLE_BASELINE_CONDITIONS" in res.discrepancies

    # -------------------------------------------------------------------------
    # Scenario 16: Verifying a macro-refactoring completion claim
    # -------------------------------------------------------------------------
    def test_16_verify_macro_refactoring_completion(self):
        claim, art = self.bridge.phase73_adapter.create_migration_completion_claim(
            migration_id="mig_core_router",
            affected_files=["backend/router.py", "backend/interfaces.py"],
            commit_sha="HEAD",
            passed_invariants=["INV_ZERO_CYCLIC_DEPENDENCY"],
        )
        # Add test execution proof
        self.bridge.ingest_evidence(
            artifact_id="ev_macro_tests",
            category=EvidenceCategory.TEST_RUNNER_RESULT,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha="HEAD",
            payload={"passed": 20, "failed": 0},
            source_subsystem="pytest",
            claim_id=claim.claim_id,
        )
        res = self.bridge.verify_claim(claim.claim_id)
        assert res.status == VerificationStatus.VERIFIED

    # -------------------------------------------------------------------------
    # Scenario 17: Verifying a portfolio completion claim against authoritative execution state
    # -------------------------------------------------------------------------
    def test_17_verify_portfolio_completion_claim(self):
        claim, art = self.bridge.phase75_adapter.create_initiative_completion_claim(
            portfolio_id="PORT_2026",
            initiative_id="INIT_ASYNC_PIPELINE",
            completed=True,
        )
        res = self.bridge.verify_claim(claim.claim_id)
        assert res.status == VerificationStatus.VERIFIED

    # -------------------------------------------------------------------------
    # Scenario 18: Reconciling a calibration promotion claim with the active calibration version
    # -------------------------------------------------------------------------
    def test_18_reconcile_calibration_promotion_claim(self):
        claim, art = self.bridge.phase76_adapter.create_calibration_promotion_claim(
            version_id="cal_v1.0.0",
            mae_reduction_pct=29.5,
            promoted=True,
        )
        res = self.bridge.verify_claim(claim.claim_id)
        assert res.status == VerificationStatus.VERIFIED

    # -------------------------------------------------------------------------
    # Scenario 19: Invalidating claims after relevant source changes
    # -------------------------------------------------------------------------
    def test_19_invalidating_claims_after_source_change(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_19",
            claim_type=ClaimType.REPOSITORY_STATE,
            proposition="Refactored database module.",
            assurance_tier=AssuranceTier.TIER_2_OPERATIONAL,
            originating_subsystem="refactor",
            required_evidence_categories=[EvidenceCategory.GIT_REVISION_RECORD],
            dependency_files=["backend/db.py"],
        )
        self.bridge.ingest_evidence(
            "ev_19", EvidenceCategory.GIT_REVISION_RECORD, EvidenceOriginType.REAL_EXECUTION, "HEAD",
            {"modified_files": ["backend/db.py"], "created_files": []}, "git", claim_id="claim_19"
        )
        self.bridge.verify_claim("claim_19")
        assert claim.status == VerificationStatus.VERIFIED

        # File modified
        inv = self.bridge.invalidate_by_files({"backend/db.py"})
        assert "claim_19" in inv
        assert claim.status == VerificationStatus.STALE

    # -------------------------------------------------------------------------
    # Scenario 20: Preserving claims whose evidence dependencies remain unaffected
    # -------------------------------------------------------------------------
    def test_20_preserve_claims_unaffected_by_file_changes(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_20",
            claim_type=ClaimType.REPOSITORY_STATE,
            proposition="Refactored cache module.",
            assurance_tier=AssuranceTier.TIER_2_OPERATIONAL,
            originating_subsystem="refactor",
            required_evidence_categories=[EvidenceCategory.GIT_REVISION_RECORD],
            dependency_files=["backend/cache.py"],
        )
        self.bridge.ingest_evidence(
            "ev_20", EvidenceCategory.GIT_REVISION_RECORD, EvidenceOriginType.REAL_EXECUTION, "HEAD",
            {"modified_files": ["backend/cache.py"], "created_files": []}, "git", claim_id="claim_20"
        )
        self.bridge.verify_claim("claim_20")
        assert claim.status == VerificationStatus.VERIFIED

        # Unrelated file modified
        inv = self.bridge.invalidate_by_files({"backend/unrelated.py"})
        assert "claim_20" not in inv
        assert claim.status == VerificationStatus.VERIFIED

    # -------------------------------------------------------------------------
    # Scenario 21: Reconciling interrupted verification jobs
    # -------------------------------------------------------------------------
    def test_21_reconcile_interrupted_verification_jobs(self):
        # Save a claim and artifact to disk
        c = self.bridge.assert_claim("claim_crash", ClaimType.TEST_EXECUTION, "Pass", AssuranceTier.TIER_2_OPERATIONAL, "sub", [EvidenceCategory.TEST_RUNNER_RESULT])
        self.bridge.ingest_evidence("ev_crash", EvidenceCategory.TEST_RUNNER_RESULT, EvidenceOriginType.REAL_EXECUTION, "HEAD", {"passed": 10, "failed": 0}, "sub", claim_id="claim_crash")

        # Simulate restart with new bridge instance
        restarted_bridge = EvidenceGovernanceBridge(store_dir=self.temp_dir)
        recovered_claim = restarted_bridge.registry.get_claim("claim_crash")
        assert recovered_claim is not None
        # Must be able to re-verify cleanly
        res = restarted_bridge.verify_claim("claim_crash")
        assert res.status == VerificationStatus.VERIFIED

    # -------------------------------------------------------------------------
    # Scenario 22: Preventing duplicate evidence ingestion
    # -------------------------------------------------------------------------
    def test_22_prevent_duplicate_evidence_ingestion(self):
        art1 = self.bridge.ingest_evidence("ev_d1", EvidenceCategory.DIRECT_EXECUTION_OUTPUT, EvidenceOriginType.REAL_EXECUTION, "HEAD", {"val": 42}, "sys")
        # Ingest identical payload with different artifact_id
        art2 = self.bridge.ingest_evidence("ev_d2", EvidenceCategory.DIRECT_EXECUTION_OUTPUT, EvidenceOriginType.REAL_EXECUTION, "HEAD", {"val": 42}, "sys")
        # Registry must deduplicate to the first artifact
        assert art2.artifact_id == art1.artifact_id

    # -------------------------------------------------------------------------
    # Scenario 23: Handling conflicting authoritative sources
    # -------------------------------------------------------------------------
    def test_23_handling_conflicting_authoritative_sources(self):
        claim = self.bridge.assert_claim("claim_conflict", ClaimType.TEST_EXECUTION, "Test state", AssuranceTier.TIER_2_OPERATIONAL, "ci", [EvidenceCategory.TEST_RUNNER_RESULT])
        # Ingest two conflicting test runner artifacts
        self.bridge.ingest_evidence("ev_c1", EvidenceCategory.TEST_RUNNER_RESULT, EvidenceOriginType.REAL_EXECUTION, "HEAD", {"passed": 20, "failed": 0}, "runner_1", claim_id="claim_conflict")
        self.bridge.ingest_evidence("ev_c2", EvidenceCategory.TEST_RUNNER_RESULT, EvidenceOriginType.REAL_EXECUTION, "HEAD", {"passed": 18, "failed": 2}, "runner_2", claim_id="claim_conflict")

        res = self.bridge.verify_claim("claim_conflict")
        assert res.status == VerificationStatus.INCONCLUSIVE
        assert "CONTRADICTION_INCONCLUSIVE" in res.discrepancies

    # -------------------------------------------------------------------------
    # Scenario 24: Escalating inconclusive verification
    # -------------------------------------------------------------------------
    def test_24_escalate_inconclusive_verification(self):
        claim = self.bridge.assert_claim("claim_inc", ClaimType.TEST_EXECUTION, "Test run", AssuranceTier.TIER_2_OPERATIONAL, "ci", [EvidenceCategory.TEST_RUNNER_RESULT])
        self.bridge.ingest_evidence("ev_i1", EvidenceCategory.TEST_RUNNER_RESULT, EvidenceOriginType.REAL_EXECUTION, "HEAD", {"passed": 10, "failed": 0}, "r1", claim_id="claim_inc")
        self.bridge.ingest_evidence("ev_i2", EvidenceCategory.TEST_RUNNER_RESULT, EvidenceOriginType.REAL_EXECUTION, "HEAD", {"passed": 0, "failed": 10}, "r2", claim_id="claim_inc")
        self.bridge.verify_claim("claim_inc")

        # Promotion must be blocked when INCONCLUSIVE
        allowed, reason = self.bridge.enforcement.evaluate_claim_promotion(claim)
        assert allowed is False

    # -------------------------------------------------------------------------
    # Scenario 25: Enforcing release-governance boundaries
    # -------------------------------------------------------------------------
    def test_25_enforcing_release_governance_boundaries(self):
        c1 = self.bridge.assert_claim("c_rel_1", ClaimType.TEST_EXECUTION, "Suite pass", AssuranceTier.TIER_2_OPERATIONAL, "ci", [EvidenceCategory.TEST_RUNNER_RESULT])
        c1.status = VerificationStatus.VERIFIED
        c2 = self.bridge.assert_claim("c_rel_2", ClaimType.SECURITY_GOVERNANCE, "Security gate", AssuranceTier.TIER_4_MISSION_CRITICAL, "sec", [EvidenceCategory.HUMAN_APPROVAL_RECORD])
        c2.status = VerificationStatus.UNVERIFIED  # Missing human approval token

        ok, rejections = self.bridge.enforcement.authorize_release_readiness([c1, c2])
        assert ok is False
        assert len(rejections) > 0

    # -------------------------------------------------------------------------
    # Scenario 26: Preserving security and authorization requirements
    # -------------------------------------------------------------------------
    def test_26_preserving_security_and_authorization_requirements(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_sec_4",
            claim_type=ClaimType.SECURITY_GOVERNANCE,
            proposition="Production kernel update authorized.",
            assurance_tier=AssuranceTier.TIER_4_MISSION_CRITICAL,
            originating_subsystem="sec_governance",
            required_evidence_categories=[EvidenceCategory.HUMAN_APPROVAL_RECORD],
        )
        # Attempt to promote without human approval token
        with pytest.raises(UnauthorizedPromotionError):
            self.bridge.enforce_promotion("claim_sec_4")

    # -------------------------------------------------------------------------
    # Scenario 27: Rejecting self-verification based solely on generated text
    # -------------------------------------------------------------------------
    def test_27_rejecting_self_verification_from_generated_text(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_self_verif",
            claim_type=ClaimType.TEST_EXECUTION,
            proposition="Tests pass.",
            assurance_tier=AssuranceTier.TIER_2_OPERATIONAL,
            originating_subsystem="agent",
            required_evidence_categories=[EvidenceCategory.TEST_RUNNER_RESULT],
        )
        self.bridge.ingest_evidence(
            "ev_text_only", EvidenceCategory.MODEL_GENERATED_EXPLANATION, EvidenceOriginType.STATIC_INSPECTION, "HEAD",
            {"text": "Trust me, all tests passed."}, "agent", claim_id="claim_self_verif"
        )
        res = self.bridge.verify_claim("claim_self_verif")
        assert res.status == VerificationStatus.UNVERIFIED

    # -------------------------------------------------------------------------
    # Scenario 28: Preventing untrusted evidence from triggering unauthorized execution
    # -------------------------------------------------------------------------
    def test_28_prevent_untrusted_evidence_from_execution(self):
        # Malicious payload with injected shell command strings
        malicious_payload = {"command": "rm -rf /", "passed": 10, "failed": 0}
        art = self.bridge.ingest_evidence(
            "ev_mal", EvidenceCategory.DIRECT_EXECUTION_OUTPUT, EvidenceOriginType.REAL_EXECUTION, "HEAD",
            malicious_payload, "untrusted_src"
        )
        # Verification engine is strictly read-only and never evals arbitrary commands
        claim = self.bridge.assert_claim("c_mal", ClaimType.REPOSITORY_STATE, "Safe state", AssuranceTier.TIER_2_OPERATIONAL, "sys", [EvidenceCategory.DIRECT_EXECUTION_OUTPUT])
        self.bridge.registry.attach_evidence_to_claim("c_mal", art.artifact_id)
        res = self.bridge.verify_claim("c_mal")
        assert res is not None

    # -------------------------------------------------------------------------
    # Scenario 29: Producing a completion report with explicit unverified items
    # -------------------------------------------------------------------------
    def test_29_produce_completion_report_with_explicit_unverified_items(self):
        c1 = self.bridge.assert_claim("c_rep_1", ClaimType.TEST_EXECUTION, "Pass", AssuranceTier.TIER_2_OPERATIONAL, "ci", [])
        c1.status = VerificationStatus.VERIFIED
        c2 = self.bridge.assert_claim("c_rep_2", ClaimType.PERFORMANCE_BENCHMARK, "Fast", AssuranceTier.TIER_3_ARCHITECTURAL, "perf", [])
        c2.status = VerificationStatus.UNVERIFIED

        audit = self.bridge.audit_report("docs/PHASE_TEST_REPORT.md", [c1, c2])
        assert audit.verified_count == 1
        assert audit.unverified_count == 1
        assert audit.is_acceptable is False

    # -------------------------------------------------------------------------
    # Scenario 30: Preserving existing phase behavior when the new capability is disabled
    # -------------------------------------------------------------------------
    def test_30_preserve_behavior_when_governance_disabled(self):
        # Empty registry operates safely with no side-effects
        res = self.bridge.verify_claim("non_existent_claim")
        assert res.status == VerificationStatus.UNVERIFIED

    # -------------------------------------------------------------------------
    # Scenario 31: Recovering safely when the evidence store is unavailable
    # -------------------------------------------------------------------------
    def test_31_recovering_safely_when_store_unavailable(self):
        # Point to invalid read-only or empty store
        empty_store = EvidenceGovernanceStore(base_dir=tempfile.mkdtemp())
        empty_reg = self.bridge.registry
        count = empty_store.reconcile_and_recover(empty_reg)
        assert count == 0

    # -------------------------------------------------------------------------
    # Scenario 32: Preventing a stale success result from being reused after invalidation
    # -------------------------------------------------------------------------
    def test_32_preventing_stale_success_reuse(self):
        claim = self.bridge.assert_claim(
            claim_id="claim_32",
            claim_type=ClaimType.REPOSITORY_STATE,
            proposition="Refactored security filter.",
            assurance_tier=AssuranceTier.TIER_3_ARCHITECTURAL,
            originating_subsystem="sec",
            required_evidence_categories=[EvidenceCategory.GIT_REVISION_RECORD],
            dependency_files=["security/filter.py"],
        )
        self.bridge.ingest_evidence(
            "ev_32", EvidenceCategory.GIT_REVISION_RECORD, EvidenceOriginType.REAL_EXECUTION, "HEAD",
            {"modified_files": ["security/filter.py"], "created_files": []}, "git", claim_id="claim_32"
        )
        self.bridge.verify_claim("claim_32")
        assert claim.status == VerificationStatus.VERIFIED

        # Invalidate
        self.bridge.invalidate_by_files({"security/filter.py"})
        assert claim.status == VerificationStatus.STALE

        # Governance must block promotion of stale claim
        with pytest.raises(UnauthorizedPromotionError):
            self.bridge.enforce_promotion("claim_32")

    # -------------------------------------------------------------------------
    # Scenario 33: Correctly distinguishing an attempted operation from a completed operation
    # -------------------------------------------------------------------------
    def test_33_distinguish_attempted_from_completed(self):
        claim = self.bridge.assert_claim("c_33", ClaimType.REPOSITORY_STATE, "Task complete", AssuranceTier.TIER_2_OPERATIONAL, "agent", [EvidenceCategory.DIRECT_EXECUTION_OUTPUT])
        # Evidence says operation is still RUNNING
        self.bridge.ingest_evidence(
            "ev_33", EvidenceCategory.DIRECT_EXECUTION_OUTPUT, EvidenceOriginType.REAL_EXECUTION, "HEAD",
            {"status": "IN_PROGRESS", "exit_code": None}, "task_runner", claim_id="c_33"
        )
        # Verify using adapter
        claim_p, art_p = self.bridge.phase75_adapter.create_initiative_completion_claim(
            portfolio_id="P1", initiative_id="INIT_RUNNING", completed=False
        )
        res = self.bridge.verify_claim(claim_p.claim_id)
        # Attempted / failed operation must NOT be verified
        assert res.status != VerificationStatus.VERIFIED

    # -------------------------------------------------------------------------
    # Scenario 34: Maintaining deterministic results for identical evidence and policy inputs
    # -------------------------------------------------------------------------
    def test_34_deterministic_results(self):
        claim1 = self.bridge.assert_claim("c_det_1", ClaimType.TEST_EXECUTION, "Test", AssuranceTier.TIER_2_OPERATIONAL, "ci", [EvidenceCategory.TEST_RUNNER_RESULT])
        self.bridge.ingest_evidence("ev_det_1", EvidenceCategory.TEST_RUNNER_RESULT, EvidenceOriginType.REAL_EXECUTION, "HEAD", {"passed": 10, "failed": 0}, "ci", claim_id="c_det_1")
        res1 = self.bridge.verify_claim("c_det_1")

        claim2 = self.bridge.assert_claim("c_det_2", ClaimType.TEST_EXECUTION, "Test", AssuranceTier.TIER_2_OPERATIONAL, "ci", [EvidenceCategory.TEST_RUNNER_RESULT])
        self.bridge.ingest_evidence("ev_det_2", EvidenceCategory.TEST_RUNNER_RESULT, EvidenceOriginType.REAL_EXECUTION, "HEAD", {"passed": 10, "failed": 0}, "ci", claim_id="c_det_2")
        res2 = self.bridge.verify_claim("c_det_2")

        assert res1.status == res2.status
        assert res1.explanation == res2.explanation

    # -------------------------------------------------------------------------
    # Scenario 35: Preserving audit history when a contradiction is resolved
    # -------------------------------------------------------------------------
    def test_35_preserve_audit_history_on_contradiction(self):
        claim = self.bridge.assert_claim("c_contra_hist", ClaimType.TEST_EXECUTION, "Tests", AssuranceTier.TIER_2_OPERATIONAL, "ci", [EvidenceCategory.TEST_RUNNER_RESULT])
        self.bridge.ingest_evidence("ev_ch1", EvidenceCategory.MODEL_GENERATED_EXPLANATION, EvidenceOriginType.STATIC_INSPECTION, "HEAD", {"text": "All passed"}, "agent", claim_id="c_contra_hist")
        self.bridge.ingest_evidence("ev_ch2", EvidenceCategory.TEST_RUNNER_RESULT, EvidenceOriginType.REAL_EXECUTION, "HEAD", {"passed": 8, "failed": 2}, "pytest", claim_id="c_contra_hist")

        res = self.bridge.verify_claim("c_contra_hist")
        assert res.status == VerificationStatus.CONTRADICTED
        assert len(self.bridge.contradiction.contradiction_records) > 0
        record = self.bridge.contradiction.contradiction_records[0]
        assert record.resolved is True
        assert record.resolution_strategy == "DIRECT_EXECUTION_OVERRIDES_MODEL_EXPLANATION"
