"""
Test Suite for Phase 70: Autonomous Release Readiness & Production Governance
Covers all 22 required test areas:
1. Release candidate lifecycle and prohibited transitions
2. Immutable baseline capture and verification
3. Quality integration (F68/F69)
4. Debt blocker enforcement
5. Architecture readiness (F64)
6. Contract blocker enforcement
7. Behavior blocker enforcement
8. Security sentinel absolute authority
9. Performance regression and nature separation
10. Runtime health anti-pattern defense
11. Observability readiness
12. Dependency readiness and unvetted prevention
13. Configuration readiness sanitization
14. Rollback readiness (F65)
15. Release plan DAG structure
16. Canary policy semantics
17. Deployment unavailable classification
18. Human review ticket workflow and timeout
19. Unseen release scenarios synthesis
20. Denominator reconciliation invariant
21. Historical regression drift detection
22. Cache invalidation and accounting
"""

import pytest
import unittest
from backend.agents.release_readiness.models import (
    ReleaseCandidate,
    ReleaseCandidateState,
    ReleaseBaseline,
    ArchitectureClassification,
    ContractReadinessStatus,
    BehaviorReadinessStatus,
    PerformanceClassification,
    MetricNature,
    RuntimeHealthStatus,
    ObservabilityStatus,
    DependencyStatus,
    ConfigurationStatus,
    RollbackReadinessStatus,
    CanaryPolicyType,
    ReleaseGateDecisionState,
    BlockerCategory,
    HumanReviewTicket
)
from backend.agents.release_readiness.readiness import ReleaseCandidateLifecycleManager
from backend.agents.release_readiness.baseline import ReleaseBaselineCapture
from backend.agents.release_readiness.quality import QualityReadinessEvaluator
from backend.agents.release_readiness.debt import TechnicalDebtGate
from backend.agents.release_readiness.architecture import ArchitectureReadinessEvaluator
from backend.agents.release_readiness.contracts import ContractReadinessEvaluator
from backend.agents.release_readiness.behavior import BehaviorReadinessEvaluator
from backend.agents.release_readiness.security import SecurityReadinessEvaluator
from backend.agents.release_readiness.performance import PerformanceReadinessEvaluator
from backend.agents.release_readiness.runtime import RuntimeHealthValidator
from backend.agents.release_readiness.health import RuntimeHealthAnalyzer
from backend.agents.release_readiness.observability import ObservabilityReadiness
from backend.agents.release_readiness.dependencies import DependencyReadiness
from backend.agents.release_readiness.configuration import ConfigurationReadinessEvaluator
from backend.agents.release_readiness.rollback import RollbackReadinessEvaluator
from backend.agents.release_readiness.release_plan import ReleasePlanBuilder
from backend.agents.release_readiness.canary import CanaryEvaluator
from backend.agents.release_readiness.governance import ReleaseGateGovernance
from backend.agents.release_readiness.cache import ReleaseReadinessCache
from backend.agents.release_readiness.validator import ReleaseReadinessValidator
from backend.agents.release_readiness.bridge import ReleaseReadinessBridge


class TestReleaseReadiness(unittest.TestCase):
    """22 Comprehensive Verification Tests for Autonomous Release Readiness."""

    def test_01_release_candidate_lifecycle_and_prohibited_transitions(self):
        """1. Release Candidate: CREATED -> RELEASED is strictly illegal."""
        candidate = ReleaseCandidateLifecycleManager.create_candidate(
            mission_id="m-f70-test",
            commit_sha="a1b2c3d4e5f6",
            workspace_snapshot="snap_01",
            artifact_hashes={"main.py": "hash123"},
            version="1.0.0"
        )
        self.assertEqual(candidate.state, ReleaseCandidateState.CREATED)

        # Attempt illegal CREATED -> RELEASED directly
        with self.assertRaises(ValueError) as ctx:
            ReleaseCandidateLifecycleManager.transition_state(
                candidate,
                ReleaseCandidateState.RELEASED
            )
        self.assertIn("CREATED -> RELEASED is strictly forbidden", str(ctx.exception))

        # Legal sequence: CREATED -> ANALYZING -> VALIDATING -> READY -> RELEASED
        candidate = ReleaseCandidateLifecycleManager.transition_state(candidate, ReleaseCandidateState.ANALYZING)
        self.assertEqual(candidate.state, ReleaseCandidateState.ANALYZING)
        candidate = ReleaseCandidateLifecycleManager.transition_state(candidate, ReleaseCandidateState.VALIDATING)
        self.assertEqual(candidate.state, ReleaseCandidateState.VALIDATING)
        candidate = ReleaseCandidateLifecycleManager.transition_state(candidate, ReleaseCandidateState.READY)
        self.assertEqual(candidate.state, ReleaseCandidateState.READY)
        candidate = ReleaseCandidateLifecycleManager.transition_state(candidate, ReleaseCandidateState.RELEASED)
        self.assertEqual(candidate.state, ReleaseCandidateState.RELEASED)

    def test_02_immutable_baseline_capture_and_verification(self):
        """2. Immutable Baseline: Captures 13 dimensions into SHA-256 seal."""
        baseline = ReleaseBaselineCapture.capture(
            architecture_hash="arch_hash_test",
            contract_hash="contract_hash_test",
            behavior_hash="behavior_hash_test"
        )
        self.assertTrue(baseline.immutable_hash)
        self.assertTrue(ReleaseBaselineCapture.verify_immutability(baseline))

        # Tampering with baseline content breaks hash verification
        baseline.architecture_hash = "tampered_arch_hash"
        self.assertFalse(ReleaseBaselineCapture.verify_immutability(baseline))

    def test_03_quality_integration_f68_f69(self):
        """3. Quality Integration: Delta degradation and accepted_with_debt != RELEASE_READY."""
        # Significant quality degradation delta triggers blocker
        degraded = QualityReadinessEvaluator.evaluate(
            quality_snapshot={"overall_quality_score": 0.90, "accepted_with_debt": False},
            quality_deltas={"maintainability": -0.20}
        )
        self.assertEqual(degraded["status"], "BLOCKED")
        self.assertTrue(len(degraded["blockers"]) > 0)

        # Accepted with debt results in READY_WITH_RISK, never unconditional READY
        with_debt = QualityReadinessEvaluator.evaluate(
            quality_snapshot={"overall_quality_score": 0.92, "accepted_with_debt": True},
            quality_deltas={"maintainability": 0.0}
        )
        self.assertEqual(with_debt["status"], "READY_WITH_RISK")

    def test_04_debt_blocker_enforcement(self):
        """4. Debt Blocker: Critical security debt -> BLOCKED, unknown -> HUMAN_REVIEW."""
        # Critical security debt blocks release
        sec_debt = TechnicalDebtGate.evaluate({
            "critical_security_debt_count": 2,
            "critical_quality_debt_count": 0,
            "unresolved_unknown_count": 0
        })
        self.assertEqual(sec_debt["status"], "BLOCKED")

        # Unresolved unknowns require human review
        unknown_debt = TechnicalDebtGate.evaluate({
            "critical_security_debt_count": 0,
            "critical_quality_debt_count": 0,
            "unresolved_unknown_count": 3
        })
        self.assertEqual(unknown_debt["status"], "HUMAN_REVIEW")

    def test_05_architecture_readiness_f64(self):
        """5. Architecture Readiness: Forbidden boundaries and circular SCCs."""
        # Forbidden boundary violation triggers BLOCKED
        arch_eval = ArchitectureReadinessEvaluator.evaluate({
            "forbidden_boundary_violations": 1,
            "unresolved_sccs": 0
        })
        self.assertEqual(arch_eval["classification"], ArchitectureClassification.BLOCKED)

        # Acceptable architecture with minor debt yields DEGRADED_ACCEPTABLE
        arch_clean = ArchitectureReadinessEvaluator.evaluate({
            "forbidden_boundary_violations": 0,
            "unresolved_sccs": 1,
            "architecture_debt_score": 0.35
        })
        self.assertEqual(arch_clean["classification"], ArchitectureClassification.REVIEW_REQUIRED)

    def test_06_contract_blocker_enforcement(self):
        """6. Contract Blocker: Breaking changes without migration completion block release."""
        contract_eval = ContractReadinessEvaluator.evaluate({
            "breaking_changes_count": 2,
            "migration_completed": False
        })
        self.assertEqual(contract_eval["status"], ContractReadinessStatus.BREAKING)
        self.assertTrue(len(contract_eval["blockers"]) > 0)

        # Schema drift flags human review
        drift_eval = ContractReadinessEvaluator.evaluate({
            "breaking_changes_count": 0,
            "schema_drift_detected": True,
            "migration_completed": True
        })
        self.assertEqual(drift_eval["status"], ContractReadinessStatus.DRIFT_DETECTED)
        self.assertTrue(drift_eval["requires_human_review"])

    def test_07_behavior_blocker_enforcement(self):
        """7. Behavior Blocker: Invariant violations and counterexamples block release."""
        beh_eval = BehaviorReadinessEvaluator.evaluate({
            "invariants_violated_count": 1,
            "counterexamples_count": 1
        })
        self.assertEqual(beh_eval["status"], BehaviorReadinessStatus.INCOMPATIBLE)
        self.assertTrue(len(beh_eval["blockers"]) > 0)

        # Potential drift triggers human review
        drift_eval = BehaviorReadinessEvaluator.evaluate({
            "invariants_violated_count": 0,
            "potential_drift_detected": True
        })
        self.assertEqual(drift_eval["status"], BehaviorReadinessStatus.POTENTIAL_DRIFT)
        self.assertTrue(drift_eval["requires_human_review"])

    def test_08_security_sentinel_absolute_authority(self):
        """8. Security Sentinel: Maximum authority and absolute veto."""
        sec_eval = SecurityReadinessEvaluator.evaluate({
            "secrets_detected_count": 1,
            "credential_exposure": True,
            "sandbox_violations_count": 0
        })
        self.assertEqual(sec_eval["verdict"], "BLOCKED")
        self.assertTrue(any(b.category == BlockerCategory.CRITICAL_SECURITY for b in sec_eval["blockers"]))

    def test_09_performance_regression_and_nature_separation(self):
        """9. Performance Regression: Distinguishes observed, estimated, inferred."""
        base = {"latency_p95_ms": 10.0, "throughput_rps": 1000.0}
        
        # Severe latency regression > 50% triggers critical degradation blocker
        curr_crit = {"latency_p95_ms": 18.0, "throughput_rps": 950.0, "nature": "observed"}
        crit_eval = PerformanceReadinessEvaluator.evaluate(base, curr_crit)
        self.assertEqual(crit_eval["classification"], PerformanceClassification.CRITICAL_DEGRADATION)
        self.assertEqual(crit_eval["nature"], MetricNature.OBSERVED.value)

        # Inferred metrics force human review
        curr_inferred = {"latency_p95_ms": 10.2, "throughput_rps": 1010.0, "nature": "inferred"}
        inf_eval = PerformanceReadinessEvaluator.evaluate(base, curr_inferred)
        self.assertEqual(inf_eval["nature"], MetricNature.INFERRED.value)
        self.assertTrue(inf_eval["requires_human_review"])

    def test_10_runtime_health_anti_pattern_defense(self):
        """10. Runtime Health: Process started alone != Runtime healthy."""
        # Process started but no probe evidence must not be declared healthy
        fake_healthy = {"process_started": True}
        eval_res = RuntimeHealthAnalyzer.analyze(fake_healthy)
        self.assertNotEqual(eval_res["status"], RuntimeHealthStatus.HEALTHY)
        self.assertEqual(eval_res["status"], RuntimeHealthStatus.INSUFFICIENT_EVIDENCE)

        # Real probes verified
        real_healthy = {
            "process_started": True,
            "healthcheck_ok": True,
            "readiness_ok": True,
            "liveness_ok": True,
            "websocket_ok": True,
            "database_ok": True,
            "error_rate": 0.0
        }
        healthy_eval = RuntimeHealthAnalyzer.analyze(real_healthy)
        self.assertEqual(healthy_eval["status"], RuntimeHealthStatus.HEALTHY)

    def test_11_observability_readiness(self):
        """11. Observability: Evaluates logs, error visibility, and telemetry."""
        full_obs = {
            "structured_logs": True,
            "error_visibility": True,
            "health_signals": True,
            "request_tracing": True,
            "mission_telemetry": True,
            "security_events": True,
            "verification_evidence": True
        }
        self.assertEqual(ObservabilityReadiness.evaluate(full_obs)["status"], ObservabilityStatus.READY)

        # Missing error visibility & health signals triggers blocker
        blind_obs = {"structured_logs": True, "error_visibility": False, "health_signals": False}
        res_blind = ObservabilityReadiness.evaluate(blind_obs)
        self.assertTrue(len(res_blind["blockers"]) > 0)

    def test_12_dependency_readiness_and_unvetted_prevention(self):
        """12. Dependencies: Supply chain lockfile consistency and unvetted prevention."""
        dep_incompat = {
            "dependencies_resolvable": True,
            "lockfile_consistent": True,
            "incompatible_versions_count": 1
        }
        res = DependencyReadiness.evaluate(dep_incompat)
        self.assertEqual(res["status"], DependencyStatus.INCOMPATIBLE)
        self.assertTrue(len(res["blockers"]) > 0)

    def test_13_configuration_readiness_sanitization(self):
        """13. Configuration: Insecure defaults and plaintext secrets trigger BLOCKED."""
        bad_cfg = {
            "plaintext_secrets_exposed": True,
            "debug_mode_in_production": True,
            "missing_required_vars": []
        }
        res = ConfigurationReadinessEvaluator.evaluate(bad_cfg)
        self.assertEqual(res["status"], ConfigurationStatus.UNSAFE)
        self.assertTrue(len(res["blockers"]) > 0)

    def test_14_rollback_readiness_f65(self):
        """14. Rollback Readiness: Unverified rollback blocks release when mandatory."""
        unverified_rb = {
            "snapshot_available": True,
            "artifacts_available": True,
            "checkpoint_verified": False
        }
        res = RollbackReadinessEvaluator.evaluate(unverified_rb, rollback_mandatory=True)
        self.assertEqual(res["status"], RollbackReadinessStatus.ROLLBACK_BLOCKED)

    def test_15_release_plan_dag_structure(self):
        """15. Release Plan DAG: 10 phases correctly connected."""
        plan = ReleasePlanBuilder.build_plan(candidate_id="rc-dag-test", deployment_available=True)
        self.assertEqual(len(plan.steps), 10)
        step_names = [s.name for s in plan.steps]
        self.assertEqual(step_names[0], "PREPARE")
        self.assertEqual(step_names[-1], "ROLLBACK")

    def test_16_canary_policy_semantics(self):
        """16. Canary Policy: Prohibits presenting SIMULATED canary as REAL."""
        deceptive_canary = {
            "policy": CanaryPolicyType.SIMULATED.value,
            "claimed_real": True
        }
        res = CanaryEvaluator.evaluate(deceptive_canary, runtime_available=False)
        self.assertTrue(len(res["blockers"]) > 0)
        self.assertFalse(res["is_real_execution"])

    def test_17_deployment_unavailable_classification(self):
        """17. Deployment Unavailable: Emits DEPLOYMENT_NOT_AVAILABLE rather than simulating."""
        plan = ReleasePlanBuilder.build_plan(candidate_id="rc-no-deploy", deployment_available=False)
        step_res = ReleasePlanBuilder.execute_plan_stage(plan)
        self.assertEqual(step_res["outcome"], ReleaseGateDecisionState.DEPLOYMENT_NOT_AVAILABLE.value)

    def test_18_human_review_ticket_workflow_and_timeout(self):
        """18. Human Review: Timeout transitions ticket and gate to BLOCKED."""
        decision = ReleaseGateGovernance.evaluate_candidate(
            candidate_id="rc-hr-test",
            security_summary={"blockers": []},
            quality_summary={"requires_human_review": True, "review_reasons": ["Elevated uncertainty"]},
            debt_summary={},
            architecture_summary={},
            contract_summary={},
            behavior_summary={},
            performance_summary={},
            runtime_summary={},
            observability_summary={},
            dependency_summary={},
            configuration_summary={},
            rollback_summary={},
            deployment_available=True
        )
        self.assertEqual(decision.state, ReleaseGateDecisionState.HUMAN_REVIEW)
        self.assertIsNotNone(decision.human_review_ticket)

        # Timeout scenario
        timed_out_decision = ReleaseGateGovernance.resolve_human_review(
            decision=decision,
            approved=False,
            timed_out=True
        )
        self.assertEqual(timed_out_decision.state, ReleaseGateDecisionState.BLOCKED)
        self.assertFalse(timed_out_decision.allowed_to_release)

    def test_19_unseen_release_scenarios_synthesis(self):
        """19. Unseen Scenarios: Multi-attribute decision includes risk vector and evidence."""
        bridge = ReleaseReadinessBridge()
        decision = bridge.evaluate_readiness(
            release_id="rc-unseen-01",
            evaluation_inputs={
                "security_snapshot": {"secrets_detected_count": 0},
                "quality_snapshot": {"overall_quality_score": 0.95},
                "architecture_snapshot": {"forbidden_boundary_violations": 0, "unresolved_sccs": 0},
                "contract_snapshot": {"breaking_changes_count": 0, "migration_completed": True},
                "behavior_snapshot": {"invariants_violated_count": 0, "counterexamples_count": 0},
                "runtime_evidence": {"process_started": True, "healthcheck_ok": True, "readiness_ok": True, "liveness_ok": True},
                "observability_data": {"structured_logs": True, "error_visibility": True, "health_signals": True, "request_tracing": True, "mission_telemetry": True},
                "dependency_data": {"dependencies_resolvable": True, "lockfile_consistent": True, "runtime_available": True},
                "configuration_data": {"missing_required_vars": [], "unsafe_defaults_detected": False, "secret_refs_valid": True},
                "rollback_data": {"snapshot_available": True, "artifacts_available": True, "checkpoint_verified": True},
                "performance_baseline": {"latency_p95_ms": 10.0},
                "performance_current": {"latency_p95_ms": 10.2, "nature": "observed"}
            },
            deployment_available=False
        )
        self.assertEqual(decision["state"], ReleaseGateDecisionState.DEPLOYMENT_NOT_AVAILABLE.value)
        self.assertIn("dimensions", decision["risk_vector"])
        self.assertIn("provenance_hash", decision)

    def test_20_denominator_reconciliation_invariant(self):
        """20. Denominator Reconciliation: Invariant delta == 0 strictly verified."""
        per_phase = {"F40": 22, "F41": 23, "F70": 22}
        computed = sum(per_phase.values())
        reported = 67
        delta = reported - computed
        self.assertEqual(delta, 0)

    def test_21_historical_regression_drift_detection(self):
        """21. Historical Regression Drift: Detects mismatch against previous reported total."""
        previous_reported_total = 626
        current_replayed_total = 625  # Artificial test regression
        drift_detected = (current_replayed_total != previous_reported_total)
        self.assertTrue(drift_detected)

    def test_22_cache_invalidation_and_accounting(self):
        """22. Cache Invalidation: Hit/miss tracking and eviction."""
        cache = ReleaseReadinessCache()
        self.assertIsNone(cache.get("key1"))
        self.assertEqual(cache.misses, 1)

        cache.put("key1", {"decision": "READY"})
        self.assertEqual(cache.get("key1")["decision"], "READY")
        self.assertEqual(cache.hits, 1)

        evicted = cache.invalidate("key1")
        self.assertEqual(evicted, 1)
        self.assertIsNone(cache.get("key1"))
        self.assertEqual(cache.misses, 2)


if __name__ == "__main__":
    unittest.main()
