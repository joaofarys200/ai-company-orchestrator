"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Unit test suite covering all 22 required test scenarios.
"""

import unittest
import time
from backend.agents.quality_debt_remediation import (
    QualityDebtRemediationBridge,
    DebtValidator,
    ValidationStatus,
    DebtRootCauseEngine,
    RootCauseCategory,
    RemediationOptionsGenerator,
    RemediationOptionType,
    QualityImpactPredictor,
    QualityImpactClassification,
    DebtContractEvaluator,
    ContractStatus,
    DebtBehaviorEvaluator,
    BehaviorStatus,
    SafeImplementationEngine,
    ImplementationStatus,
    RemediationCoordinator,
    RemediationPlanner,
    QualityComparisonEngine,
    QualityComparisonOutcome,
    DebtResolutionGovernor,
    ResolutionStatus,
    DebtDefermentManager,
    QualityGamingDetector,
    GamingType,
    RemediationConvergenceDetector,
    ConvergenceState,
    RemediationRollbackEngine,
    RemediationCache,
    Phase69Validator,
    DebtIngestionEngine,
)


class TestQualityDebtRemediation(unittest.TestCase):
    def setUp(self):
        self.bridge = QualityDebtRemediationBridge(db_path=":memory:")

    # 1. debt validation
    def test_01_debt_validation(self):
        item = self.bridge.ingestion_engine.ingest({
            "debt_id": "debt_test_01",
            "category": "CODE",
            "severity": "HIGH",
            "affected_surface": "backend.api",
            "evidence": {"complexity": 18},
            "confidence": 0.85,
        })
        res = self.bridge.validator.validate(item)
        self.assertEqual(res.status, ValidationStatus.VALID_DEBT)
        self.assertTrue(res.evidence_validity)

        # Invalidate when surface does not exist
        res_invalid = self.bridge.validator.validate(item, codebase_surface_exists=False)
        self.assertEqual(res_invalid.status, ValidationStatus.INVALID_DEBT)

    # 2. root cause
    def test_02_root_cause(self):
        item_arch = self.bridge.ingestion_engine.ingest({
            "debt_id": "debt_test_02_arch",
            "category": "ARCHITECTURAL",
            "severity": "HIGH",
            "affected_surface": "backend.agents.scc",
            "evidence": {"scc_cycle": True},
        })
        cause_arch = self.bridge.root_cause_engine.analyze(item_arch)
        self.assertEqual(cause_arch.category, RootCauseCategory.ARCHITECTURAL_CAUSE)

        item_unk = self.bridge.ingestion_engine.ingest({
            "debt_id": "debt_test_02_unk",
            "category": "MISCELLANEOUS_ANOMALY",
            "severity": "LOW",
            "affected_surface": "unknown_file.py",
            "evidence": {"note": "random anomaly"},
        })
        cause_unk = self.bridge.root_cause_engine.analyze(item_unk)
        self.assertEqual(cause_unk.category, RootCauseCategory.UNKNOWN_CAUSE)

    # 3. remediation options
    def test_03_remediation_options(self):
        item = self.bridge.ingestion_engine.ingest({
            "debt_id": "debt_test_03",
            "category": "ARCHITECTURAL",
            "severity": "HIGH",
            "affected_surface": "backend.graph",
            "evidence": {"cycle": True},
        })
        cause = self.bridge.root_cause_engine.analyze(item)
        options = self.bridge.options_generator.generate_options(item, cause)
        self.assertGreaterEqual(len(options), 2)
        opt_types = [o.option_type for o in options]
        self.assertIn(RemediationOptionType.KEEP_CURRENT, opt_types)
        self.assertIn(RemediationOptionType.DEPENDENCY_INVERSION, opt_types)

    # 4. quality impact
    def test_04_quality_impact(self):
        item = self.bridge.ingestion_engine.ingest({
            "debt_id": "debt_test_04",
            "category": "SECURITY",
            "severity": "CRITICAL",
            "affected_surface": "backend.security.auth",
            "evidence": {"unvalidated_jwt": True},
        })
        cause = self.bridge.root_cause_engine.analyze(item)
        options = self.bridge.options_generator.generate_options(item, cause)
        sec_opt = next(o for o in options if o.option_type == RemediationOptionType.SECURITY_HARDENING)
        prediction = self.bridge.impact_predictor.predict_impact(sec_opt)
        self.assertEqual(prediction.dimension_impacts["SECURITY"], QualityImpactClassification.IMPROVEMENT_EXPECTED)

    # 5. contract validation
    def test_05_contract_validation(self):
        evaluator = DebtContractEvaluator()
        before = {"GET /api/v1/data": "ResponseModelV1", "POST /api/v1/submit": "SubmitModel"}
        after_compatible = {"GET /api/v1/data": "ResponseModelV1", "POST /api/v1/submit": "SubmitModel", "GET /api/v2/data": "ResponseModelV2"}
        after_breaking = {"GET /api/v2/data": "ResponseModelV2"}  # removed endpoints

        rep_comp = evaluator.evaluate_contract_change("api_surface", before, after_compatible)
        self.assertEqual(rep_comp.status, ContractStatus.COMPATIBLE)
        self.assertFalse(rep_comp.requires_approval)

        rep_break = evaluator.evaluate_contract_change("api_surface", before, after_breaking)
        self.assertEqual(rep_break.status, ContractStatus.BREAKING)
        self.assertTrue(rep_break.requires_approval)

    # 6. behavior validation
    def test_06_behavior_validation(self):
        evaluator = DebtBehaviorEvaluator()
        rep_ok = evaluator.evaluate_behavior("state_machine")
        self.assertEqual(rep_ok.status, BehaviorStatus.PRESERVED)
        self.assertFalse(rep_ok.routes_to_human_review)

        # Counterexample triggers INCOMPATIBLE
        rep_counter = evaluator.evaluate_behavior("state_machine", has_counterexample=True)
        self.assertEqual(rep_counter.status, BehaviorStatus.INCOMPATIBLE)
        self.assertTrue(rep_counter.routes_to_human_review)

        # Broken invariant triggers POTENTIAL_DRIFT -> routes to human review by default
        rep_drift = evaluator.evaluate_behavior("state_machine", invariant_checks={"invariants": False, "ordering": True, "retries": True, "concurrency": True, "idempotency": True, "state_transitions": True})
        self.assertEqual(rep_drift.status, BehaviorStatus.POTENTIAL_DRIFT)
        self.assertTrue(rep_drift.routes_to_human_review)

    # 7. safe implementation
    def test_07_safe_implementation(self):
        engine = SafeImplementationEngine()
        res_ok = engine.execute_transactional_patch(["module_a.py"])
        self.assertEqual(res_ok.status, ImplementationStatus.SUCCESS)
        self.assertTrue(res_ok.build_passed)
        self.assertTrue(res_ok.test_passed)

        res_fail = engine.execute_transactional_patch(["module_b.py"], simulate_build_failure=True)
        self.assertEqual(res_fail.status, ImplementationStatus.FAILED)
        self.assertFalse(res_fail.build_passed)

    # 8. multi-agent coordination
    def test_08_multi_agent_coordination(self):
        coordinator = RemediationCoordinator()
        plan = coordinator.create_coordination_plan("mission_101", "debt_101", ["surface_a.py"])
        self.assertEqual(len(plan.intents), 4)
        types = [i.intent_type.value for i in plan.intents]
        self.assertIn("ANALYSIS_INTENT", types)
        self.assertIn("IMPLEMENTATION_INTENT", types)
        self.assertIn("TEST_INTENT", types)
        self.assertIn("VERIFICATION_INTENT", types)
        self.assertFalse(plan.has_conflicts)

    # 9. mission creation
    def test_09_mission_creation(self):
        item = self.bridge.ingestion_engine.ingest({
            "debt_id": "debt_test_09",
            "category": "CODE",
            "severity": "MEDIUM",
            "affected_surface": "backend.core",
            "evidence": {"complexity": 14},
        })
        cause = self.bridge.root_cause_engine.analyze(item)
        opts = self.bridge.options_generator.generate_options(item, cause)
        plan = self.bridge.planner.create_plan(item, opts[0])
        mission = self.bridge.planner.create_mission(plan)
        self.assertEqual(mission.debt_id, item.debt_id)
        self.assertEqual(mission.plan_id, plan.plan_id)
        self.assertEqual(mission.status, "INITIALIZED")

    # 10. quality rescan
    def test_10_quality_rescan(self):
        engine = QualityComparisonEngine()
        q_before = {dim: 0.60 for dim in engine.DIMENSIONS}
        q_after_imp = {dim: 0.85 for dim in engine.DIMENSIONS}
        res = engine.compare_quality("debt_10", q_before, q_after_imp)
        self.assertEqual(res.outcome, QualityComparisonOutcome.REAL_IMPROVEMENT)
        self.assertEqual(len(res.improved_dimensions), 9)

        # No change
        res_no = engine.compare_quality("debt_10", q_before, q_before)
        self.assertEqual(res_no.outcome, QualityComparisonOutcome.NO_MEASURABLE_CHANGE)

    # 11. resolution
    def test_11_resolution(self):
        res = self.bridge.process_debt_lifecycle({
            "debt_id": "debt_test_11",
            "category": "CODE",
            "severity": "LOW",
            "affected_surface": "backend.utils",
            "evidence": {"lint_issue": True},
        })
        self.assertEqual(res["resolution"]["status"], ResolutionStatus.RESOLVED.value)
        self.assertTrue(res["resolution"]["original_evidence_invalidated"])

    # 12. partial resolution
    def test_12_partial_resolution(self):
        res = self.bridge.process_debt_lifecycle(
            {
                "debt_id": "debt_test_12",
                "category": "ARCHITECTURAL",
                "severity": "HIGH",
                "affected_surface": "backend.arch",
                "evidence": {"hotspots": 3},
            },
            partial_hotspots=[{"debt_id": "debt_test_12_child_1", "affected_surface": "backend.arch.sub1"}],
        )
        self.assertEqual(res["resolution"]["status"], ResolutionStatus.PARTIALLY_RESOLVED.value)
        self.assertEqual(len(res["resolution"]["remaining_child_debts"]), 1)

    # 13. deferment
    def test_13_deferment(self):
        mgr = DebtDefermentManager()
        deferment = mgr.create_deferment(
            debt_id="debt_test_13",
            reason="Scheduled for refactoring in Sprint 70",
            risk=0.45,
            expected_cost=5.0,
            revisit_condition="Sprint 70 Sprint Planning",
        )
        self.assertEqual(deferment.debt_id, "debt_test_13")
        self.assertIsNotNone(mgr.get_deferment("debt_test_13"))
        self.assertEqual(len(mgr.list_all_deferments()), 1)

    # 14. gaming detection
    def test_14_gaming_detection(self):
        detector = QualityGamingDetector()
        event_test = detector.detect_gaming(actor="Agent_Rogue", deleted_test_files=["tests/test_core.py"])
        self.assertIsNotNone(event_test)
        self.assertEqual(event_test.gaming_type, GamingType.TEST_DELETION)
        self.assertTrue(event_test.blocked)

        event_scope = detector.detect_gaming(actor="Agent_Rogue", excluded_scope_paths=["backend/sensitive.py"])
        self.assertIsNotNone(event_scope)
        self.assertEqual(event_scope.gaming_type, GamingType.SCOPE_EXCLUSION)

    # 15. security gate
    def test_15_security_gate(self):
        detector = QualityGamingDetector()
        res_violation = detector.validate_security_invariants(
            target_files=["backend/sentinel/policy.py"],
            has_sentinel_mutation=True,
        )
        self.assertFalse(res_violation["security_gate_passed"])
        self.assertTrue(res_violation["hard_blocked"])

    # 16. convergence
    def test_16_convergence(self):
        detector = RemediationConvergenceDetector(max_attempts=3, max_rollbacks=2)
        rep1 = detector.evaluate("debt_16", attempt_count=1, rollback_count=0)
        self.assertEqual(rep1.state, ConvergenceState.CONVERGING)
        self.assertFalse(rep1.halt_required)

        rep_blocked = detector.evaluate("debt_16", attempt_count=2, rollback_count=2)
        self.assertEqual(rep_blocked.state, ConvergenceState.BLOCKED)
        self.assertTrue(rep_blocked.halt_required)

    # 17. rollback
    def test_17_rollback(self):
        rollback_engine = RemediationRollbackEngine()
        pre_hashes = {"file1.py": "hash_123", "file2.py": "hash_456"}
        res = rollback_engine.execute_rollback("tx_99", "debt_17", ["file1.py", "file2.py"], pre_hashes)
        self.assertTrue(res.success)
        self.assertTrue(res.state_reconciled)

        res_fail = rollback_engine.execute_rollback("tx_99", "debt_17", ["file1.py"], pre_hashes, simulated_hash_mismatch=True)
        self.assertFalse(res_fail.success)
        self.assertFalse(res_fail.state_reconciled)

    # 18. unseen debt mission
    def test_18_unseen_debt_mission(self):
        res = self.bridge.process_debt_lifecycle({
            "debt_id": "debt_unseen_flaky_test",
            "category": "TEST",
            "severity": "MEDIUM",
            "affected_surface": "tests/test_async_worker.py",
            "evidence": {"intermittent_timeout_ms": 420},
            "confidence": 0.88,
        })
        self.assertIn(res["stage"], ["LIFECYCLE_COMPLETE", "VALIDATION_FAILED"])
        self.assertIn(res["resolution"]["status"], [ResolutionStatus.RESOLVED.value, ResolutionStatus.PARTIALLY_RESOLVED.value])

    # 19. denominator reconciliation
    def test_19_denominator_reconciliation(self):
        val = Phase69Validator()
        per_phase = {"F40": 10, "F50": 20, "F60": 30, "F68": 40, "F69": 22}
        total = 122
        valid, report = val.validate_regression_reconciliation(per_phase, total, total)
        self.assertTrue(valid)
        self.assertEqual(report["delta"], 0)

        # Mismatch fails
        valid_bad, _ = val.validate_regression_reconciliation(per_phase, 120, total)
        self.assertFalse(valid_bad)

    # 20. cache invalidation
    def test_20_cache_invalidation(self):
        cache = RemediationCache()
        key = cache.generate_cache_key("dh1", "qh1", "GOVERNED", "ah1", "v1")
        cache.put(key, {"cached_result": "ok"})
        cached = cache.get(key)
        self.assertIsNotNone(cached)
        self.assertTrue(cached["__is_cached_hit__"])
        self.assertFalse(cached["__is_fresh_evidence__"])

        cleared = cache.invalidate("State change")
        self.assertEqual(cleared, 1)
        self.assertIsNone(cache.get(key))

    # 21. residual debt
    def test_21_residual_debt(self):
        res = self.bridge.process_debt_lifecycle(
            {
                "debt_id": "debt_test_21",
                "category": "ARCHITECTURAL",
                "severity": "CRITICAL",
                "affected_surface": "backend.distributed_bus",
                "evidence": {"coupling": 0.82},
            },
            partial_hotspots=[
                {"debt_id": "debt_test_21_child_a", "affected_surface": "backend.distributed_bus.consumer"},
                {"debt_id": "debt_test_21_child_b", "affected_surface": "backend.distributed_bus.producer"},
            ],
        )
        self.assertEqual(res["resolution"]["status"], ResolutionStatus.PARTIALLY_RESOLVED.value)
        self.assertEqual(len(res["resolution"]["remaining_child_debts"]), 2)

    # 22. reopened debt
    def test_22_reopened_debt(self):
        conv = RemediationConvergenceDetector()
        conv.record_event("debt_22", "RESOLVED")
        conv.record_event("debt_22", "REOPENED_AFTER_REGRESSION")
        self.assertIn("REOPENED_AFTER_REGRESSION", conv._history["debt_22"])


if __name__ == "__main__":
    unittest.main()
