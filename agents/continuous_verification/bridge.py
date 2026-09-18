"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: bridge.py
Master ContinuousVerificationBridge orchestrating the entire Continuous Verification Lifecycle:
START -> DETECT_CHANGE -> BUILD_IMPACT -> PLAN -> SELECT_TESTS -> SYNTHESIZE_MISSING
      -> QUALITY_GATE -> EXECUTE -> OBSERVE -> COVERAGE -> REGRESSION_COMPARE
      -> FLAKY_CHECK -> EVIDENCE -> DECIDE -> RECORD -> FINISHED.

Traverses all 20 mandatory verification states and produces comprehensive VerificationDecisions.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .baseline import BaselineStore
from .cache import VerificationCache
from .change_detection import ChangeDetector
from .counterexample import CounterexamplePromotionManager
from .coverage import MultidimensionalCoverageEvaluator
from .evidence import VerificationEvidenceLedger
from .executor import ContinuousTestExecutor, ExecutionResultItem
from .flaky import FlakyTestDetector
from .impact import ImpactToVerificationPlanner
from .index import VerificationIndex
from .metrics import ContinuousVerificationMetrics
from .models import (
    BaselineSnapshot,
    ChangeItem,
    ChangeSet,
    ChangeSource,
    ChangeType,
    CoverageVector,
    FlakyAnalysisResult,
    FlakyStatus,
    RegressionClassification,
    RegressionComparisonResult,
    SelectedTestItem,
    TestSelectionPlan,
    VerificationDecision,
    VerificationDecisionOutcome,
    VerificationPolicy,
    VerificationPolicyName,
    VerificationState,
    VerificationSurface,
)
from .persistence import VerificationPersistenceStore
from .planner import ContinuousVerificationPlanner, VerificationPlan
from .policy import VerificationPolicyEngine
from .regression import RegressionComparator
from .security import VerificationSecuritySentinel
from .selector import ContinuousTestSelector
from .synthesis_bridge import ContinuousSynthesisBridge
from .validator import VerificationDecisionValidator


class ContinuousVerificationBridge:
    """Unified Facade for Continuous Verification & Autonomous Regression Governance."""

    _instance: Optional[ContinuousVerificationBridge] = None

    def __init__(self, workspace_root: Optional[str] = None, db_path: Optional[str] = None) -> None:
        self.workspace_root = workspace_root or os.getcwd()
        self.change_detector = ChangeDetector(self.workspace_root)
        self.impact_planner = ImpactToVerificationPlanner(self.workspace_root)
        self.policy_engine = VerificationPolicyEngine()
        self.planner = ContinuousVerificationPlanner()
        self.counterexample_mgr = CounterexamplePromotionManager()
        self.selector = ContinuousTestSelector(self.counterexample_mgr.get_permanent_regression_ids())
        self.synthesis_bridge = ContinuousSynthesisBridge(self.workspace_root)
        self.executor = ContinuousTestExecutor(self.workspace_root)
        self.coverage_evaluator = MultidimensionalCoverageEvaluator()
        self.baseline_store = BaselineStore()
        self.regression_comparator = RegressionComparator()
        self.flaky_detector = FlakyTestDetector(self.executor)
        self.security = VerificationSecuritySentinel(self.workspace_root)
        self.cache = VerificationCache()
        self.persistence = VerificationPersistenceStore(db_path)
        self.metrics = ContinuousVerificationMetrics()
        self.index = VerificationIndex()
        self.state_history: List[VerificationState] = []

    @classmethod
    def get_instance(cls, workspace_root: Optional[str] = None, db_path: Optional[str] = None) -> ContinuousVerificationBridge:
        if cls._instance is None:
            cls._instance = cls(workspace_root, db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def verify_change(
        self,
        change_set: Optional[ChangeSet] = None,
        workspace_files: Optional[Dict[str, str]] = None,
        policy: Optional[VerificationPolicy | str] = None,
        available_tests: Optional[List[Dict[str, Any]]] = None,
        is_coverage_known: bool = True,
        is_environmental_failure: bool = False,
        domain: str = "real_repository",
    ) -> VerificationDecision:
        """
        Execute the full Continuous Verification Loop.
        Traverses all 20 mandatory verification states.
        """
        t_start = time.perf_counter()
        run_id = f"vrun_{int(time.time() * 1000)}"
        evidence_ledger = VerificationEvidenceLedger(run_id)
        metric_bucket = self.metrics.get_bucket(domain)

        active_policy = VerificationPolicyEngine.get_policy(policy)
        reasons: List[str] = []
        regressions: List[str] = []
        flaky_tests: List[str] = []

        # 1. State: INITIAL
        self.state_history = [VerificationState.INITIAL]
        self.persistence.record_run(run_id, VerificationState.INITIAL.value, active_policy.name.value)
        evidence_ledger.record_stage_evidence("INITIAL", {"run_id": run_id, "policy": active_policy.name.value})

        # 2. State: CHANGE_DETECTED
        self.state_history.append(VerificationState.CHANGE_DETECTED)
        effective_cs = change_set
        if effective_cs is None:
            effective_cs = ChangeSet(id=f"cs_empty_{int(time.time() * 1000)}", changes=[], source="none")

        self.persistence.record_change_set(run_id, effective_cs)
        change_hash = effective_cs.deterministic_hash()
        evidence_ledger.record_stage_evidence("CHANGE_DETECTED", {"change_hash": change_hash, "total_changes": len(effective_cs.changes)})

        # Central Invariant Check: NO_CHANGE -> NO_VERIFICATION
        if not effective_cs.changes:
            self.state_history.append(VerificationState.VERIFIED_WITHIN_SCOPE)
            self.state_history.append(VerificationState.FINISHED)
            metric_bucket.changes_verified += 1
            decision = VerificationDecision(
                decision_id=f"dec_{run_id}",
                outcome=VerificationDecisionOutcome.VERIFIED_WITHIN_SCOPE,
                scope={"type": "NO_CHANGE"},
                tests_run=[],
                tests_missing=[],
                coverage_before=None,
                coverage_after=None,
                regressions=[],
                flaky_tests=[],
                dynamic_boundaries=[],
                evidence=evidence_ledger.export_evidence(),
                confidence=1.0,
                reasons=["No code or artifact change detected; NO_VERIFICATION invariant applied"],
            )
            self.persistence.record_decision(run_id, decision)
            self.index.index_decision(decision)
            return decision

        # 3. State: IMPACT_ANALYSIS
        self.state_history.append(VerificationState.IMPACT_ANALYSIS)
        surface = self.impact_planner.analyze(effective_cs, workspace_files=workspace_files)
        evidence_ledger.record_stage_evidence("IMPACT_ANALYSIS", surface.to_dict())

        # Check Cache
        baseline_snap = self.baseline_store.get_latest_snapshot()
        baseline_hash = baseline_snap.snapshot_id if baseline_snap else "no_baseline"
        cache_key = self.cache.compute_cache_key(
            change_hash=change_hash,
            verification_scope=str(sorted(surface.affected_files)),
            test_hash="suite_default",
            baseline_hash=baseline_hash,
            policy_name=active_policy.name.value,
        )
        cached_decision = self.cache.get(cache_key)
        if cached_decision:
            metric_bucket.cache_hits += 1
            self.state_history.append(VerificationState.FINISHED)
            return cached_decision
        metric_bucket.cache_misses += 1

        # 4. State: PLANNING
        self.state_history.append(VerificationState.PLANNING)
        plan = self.planner.create_plan(surface, policy=active_policy, has_change=True)
        self.persistence.record_plan(run_id, plan)
        evidence_ledger.record_stage_evidence("PLANNING", plan.to_dict())

        # Central Invariant Check: CHANGE_WITH_NO_IMPACT_EVIDENCE -> UNCERTAIN
        if plan.status_signal == "UNCERTAIN":
            self.state_history.append(VerificationState.INSUFFICIENT_EVIDENCE)
            self.state_history.append(VerificationState.FINISHED)
            metric_bucket.insufficient_evidence += 1
            decision = VerificationDecision(
                decision_id=f"dec_{run_id}",
                outcome=VerificationDecisionOutcome.INSUFFICIENT_EVIDENCE,
                scope=surface.to_dict(),
                tests_run=[],
                tests_missing=["DYNAMIC_REFLECTION_PROOF"],
                coverage_before=None,
                coverage_after=None,
                regressions=[],
                flaky_tests=[],
                dynamic_boundaries=surface.dynamic_boundaries,
                evidence=evidence_ledger.export_evidence(),
                confidence=round(1.0 - surface.uncertainty, 2),
                reasons=["Change exhibits high uncertainty or unverified dynamic reflection without boundary evidence"],
            )
            self.persistence.record_decision(run_id, decision)
            return decision

        # 5. State: SELECTING
        self.state_history.append(VerificationState.SELECTING)
        selection_plan = self.selector.select_tests(surface, plan, available_tests=available_tests)
        self.persistence.record_selected_tests(run_id, selection_plan)
        evidence_ledger.record_stage_evidence("SELECTING", selection_plan.to_dict())
        metric_bucket.tests_selected += len(selection_plan.selected)
        metric_bucket.tests_skipped += len(selection_plan.skipped)

        # 6. State: SYNTHESIZING
        self.state_history.append(VerificationState.SYNTHESIZING)
        t_synth_start = time.perf_counter()
        synth_tests: List[SelectedTestItem] = []
        unresolved_gaps: List[Dict[str, Any]] = []

        if selection_plan.required_but_missing and active_policy.allow_synthesis:
            synth_tests, unresolved_gaps = self.synthesis_bridge.synthesize_missing_tests(
                surface, selection_plan.required_but_missing, max_attempts=active_policy.max_synthesis_attempts
            )
            metric_bucket.tests_synthesized += len(synth_tests)
        metric_bucket.synthesis_time_ms += (time.perf_counter() - t_synth_start) * 1000.0
        evidence_ledger.record_stage_evidence("SYNTHESIZING", {
            "synthesized_count": len(synth_tests),
            "unresolved_gaps": unresolved_gaps,
        })

        # 7. State: VALIDATING_TESTS (Quality Gate)
        self.state_history.append(VerificationState.VALIDATING_TESTS)
        all_executable_tests = list(selection_plan.selected) + synth_tests
        validated_tests: List[SelectedTestItem] = []
        blocked_tests: List[str] = []

        for t_item in all_executable_tests:
            is_safe, sec_err = self.security.validate_code_safety(t_item.test_id + " " + (t_item.file_path or ""))
            if not is_safe:
                blocked_tests.append(f"{t_item.test_id}: {sec_err}")
            else:
                validated_tests.append(t_item)

        if blocked_tests:
            evidence_ledger.record_stage_evidence("SECURITY_BLOCK", {"blocked": blocked_tests})
            self.state_history.append(VerificationState.BLOCKED)
            self.state_history.append(VerificationState.FINISHED)
            metric_bucket.changes_blocked += 1
            decision = VerificationDecision(
                decision_id=f"dec_{run_id}",
                outcome=VerificationDecisionOutcome.BLOCKED,
                scope=surface.to_dict(),
                tests_run=[],
                tests_missing=[],
                coverage_before=None,
                coverage_after=None,
                regressions=[],
                flaky_tests=[],
                dynamic_boundaries=surface.dynamic_boundaries,
                evidence=evidence_ledger.export_evidence(),
                confidence=1.0,
                reasons=[f"Security Sentinel blocked test execution: {b}" for b in blocked_tests],
            )
            self.persistence.record_decision(run_id, decision)
            return decision

        evidence_ledger.record_stage_evidence("VALIDATING_TESTS", {"validated_count": len(validated_tests)})

        # 8. State: EXECUTING
        self.state_history.append(VerificationState.EXECUTING)
        t_exec_start = time.perf_counter()
        is_economic = (active_policy.name == VerificationPolicyName.ECONOMIC)
        exec_results = self.executor.execute_suite(validated_tests, is_economic=is_economic)
        metric_bucket.execution_time_ms += (time.perf_counter() - t_exec_start) * 1000.0
        evidence_ledger.record_stage_evidence("EXECUTING", {"results": [r.to_dict() for r in exec_results]})

        # 9. State: OBSERVING
        self.state_history.append(VerificationState.OBSERVING)
        results_map = {r.test_id: r.status for r in exec_results}
        evidence_ledger.record_stage_evidence("OBSERVING", {"results_map": results_map})

        # 10. State: COVERAGE
        self.state_history.append(VerificationState.COVERAGE)
        coverage_after = self.coverage_evaluator.compute_coverage(
            surface=surface,
            executed_tests=[r.test_id for r in exec_results if r.status == "PASS"],
            is_coverage_known=is_coverage_known,
        )
        coverage_before = baseline_snap.coverage_vector if baseline_snap else CoverageVector()
        self.persistence.record_coverage(run_id, coverage_after)
        evidence_ledger.record_stage_evidence("COVERAGE", coverage_after.to_dict())

        # 11. State: FLAKY_ANALYSIS
        self.state_history.append(VerificationState.FLAKY_ANALYSIS)
        flaky_results: List[FlakyAnalysisResult] = []
        for r_item, t_item in zip(exec_results, validated_tests):
            if r_item.status in ("FAIL", "ERROR"):
                flaky_res = self.flaky_detector.analyze_test(t_item, r_item, active_policy)
                flaky_results.append(flaky_res)
                self.persistence.record_flaky(run_id, flaky_res)
                if flaky_res.status == FlakyStatus.FLAKY or flaky_res.review_required:
                    flaky_tests.append(flaky_res.test_id)
                    metric_bucket.flaky_tests += 1

        evidence_ledger.record_stage_evidence("FLAKY_ANALYSIS", {"flaky_results": [f.to_dict() for f in flaky_results]})

        # 12. State: COMPARING (Regression Comparison)
        self.state_history.append(VerificationState.COMPARING)
        total_exec_s = (time.perf_counter() - t_start)
        regression_result = self.regression_comparator.compare(
            current_results=results_map,
            current_coverage=coverage_after,
            current_duration=total_exec_s,
            baseline=baseline_snap,
            flaky_tests=flaky_tests,
            is_environmental_error=is_environmental_failure,
        )
        self.persistence.record_regression(run_id, regression_result)
        evidence_ledger.record_stage_evidence("COMPARING", regression_result.to_dict())

        if regression_result.classification == RegressionClassification.REGRESSION:
            regressions.extend(regression_result.regressed_items)
            metric_bucket.regressions_detected += len(regression_result.regressed_items)

        # 13. State: EVIDENCE_BUILDING
        self.state_history.append(VerificationState.EVIDENCE_BUILDING)
        evidence_signature = evidence_ledger.get_ledger_signature()
        evidence_ledger.record_stage_evidence("EVIDENCE_BUILDING", {"signature": evidence_signature})

        # 14. Decision Formulation
        outcome: VerificationDecisionOutcome
        confidence = 1.0

        if regressions:
            outcome = VerificationDecisionOutcome.REGRESSION_DETECTED
            reasons.append(f"Regressions detected: {', '.join(regressions[:5])}")
            self.state_history.append(VerificationState.REGRESSION_FOUND)
        elif flaky_tests:
            outcome = VerificationDecisionOutcome.FLAKY
            reasons.append(f"FLAKY_REVIEW_REQUIRED: Intermittent test failures observed: {flaky_tests}")
            metric_bucket.human_review_count += 1
            self.state_history.append(VerificationState.HUMAN_REVIEW)
        elif not validated_tests and surface.affected_files:
            outcome = VerificationDecisionOutcome.INSUFFICIENT_EVIDENCE
            reasons.append("NO_TESTS: No applicable tests selected or executed for affected surface")
            metric_bucket.insufficient_evidence += 1
            self.state_history.append(VerificationState.INSUFFICIENT_EVIDENCE)
        elif not is_coverage_known or coverage_after.line_coverage == 0.0:
            outcome = VerificationDecisionOutcome.INSUFFICIENT_EVIDENCE
            reasons.append("COVERAGE_UNKNOWN: Test coverage cannot be established; verification prohibited")
            metric_bucket.insufficient_evidence += 1
            self.state_history.append(VerificationState.INSUFFICIENT_EVIDENCE)
        elif surface.uncertainty > 0.4 and surface.dynamic_boundaries:
            outcome = VerificationDecisionOutcome.HUMAN_REVIEW
            reasons.append(f"High dynamic uncertainty ({surface.uncertainty}); requires human review")
            metric_bucket.human_review_count += 1
            self.state_history.append(VerificationState.HUMAN_REVIEW)
        else:
            outcome = VerificationDecisionOutcome.VERIFIED_WITHIN_SCOPE
            reasons.append(f"Verified within scope across {len(validated_tests)} tests with no regressions")
            metric_bucket.changes_verified += 1
            self.state_history.append(VerificationState.VERIFIED_WITHIN_SCOPE)

        # Central Invariant Validation
        decision = VerificationDecision(
            decision_id=f"dec_{run_id}",
            outcome=outcome,
            scope=surface.to_dict(),
            tests_run=[r.test_id for r in exec_results],
            tests_missing=[g.get("target_symbol", "gap") for g in unresolved_gaps],
            coverage_before=coverage_before,
            coverage_after=coverage_after,
            regressions=regressions,
            flaky_tests=flaky_tests,
            dynamic_boundaries=surface.dynamic_boundaries,
            evidence=evidence_ledger.export_evidence(),
            confidence=round(confidence, 2),
            reasons=reasons,
        )

        is_valid, inv_errors = VerificationDecisionValidator.validate_decision(
            decision=decision,
            surface=surface,
            coverage=coverage_after,
            regressions=regressions,
            flaky_tests=flaky_tests,
            is_coverage_known=is_coverage_known,
            has_dynamic_reflection=bool(surface.dynamic_boundaries),
        )

        if not is_valid:
            # Overrule outcome to prevent invalid promotion
            decision.outcome = VerificationDecisionOutcome.FAILED
            decision.reasons.extend(inv_errors)
            self.state_history.append(VerificationState.FAILED)

        # 15. Record & Finish
        self.state_history.append(VerificationState.FINISHED)
        self.persistence.record_decision(run_id, decision)
        self.index.index_decision(decision)

        # Update baseline on clean verification
        if decision.outcome == VerificationDecisionOutcome.VERIFIED_WITHIN_SCOPE:
            new_snap = self.baseline_store.create_snapshot(
                test_results=results_map,
                coverage_vector=coverage_after,
                execution_duration=total_exec_s,
                evidence_hashes=[e["data_hash"] for e in decision.evidence],
            )
            # Store in cache
            self.cache.put(cache_key, decision)
            post_key = self.cache.compute_cache_key(
                change_hash=change_hash,
                verification_scope=str(sorted(surface.affected_files)),
                test_hash="suite_default",
                baseline_hash=new_snap.snapshot_id,
                policy_name=active_policy.name.value,
            )
            self.cache.put(post_key, decision)

        metric_bucket.verification_time_ms += (time.perf_counter() - t_start) * 1000.0
        return decision
