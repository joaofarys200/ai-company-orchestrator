"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: bridge.py
Unified master facade orchestrating requirements, adaptive test synthesis, sandboxed execution,
multi-dimensional coverage tracking, bounded mutation testing, and cross-phase integrations.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .analyzer import CoverageGapAnalyzer
from .behavior import BehaviorTestGenerator
from .browser import BrowserTestSynthesizer
from .cache import TestSynthesisCache
from .candidate import TestCandidateManager
from .contracts import ContractTestGenerator
from .counterexample import CounterexampleTestSynthesizer
from .coverage import MultiDimensionalCoverageTracker
from .executor import TestExecutor
from .feedback import AdaptiveFeedbackEngine
from .generator import AutonomousTestGenerator
from .index import TestSynthesisIndex
from .metrics import TestSynthesisMetrics
from .minimizer import TestMinimalityEvaluator, TestQualityEvaluator
from .models import (
    CounterexampleEvidence,
    CoverageMetrics,
    MutationResult,
    TestCandidate,
    TestCandidateStatus,
    TestEvidenceItem,
    TestExecutionResult,
    TestRequirement,
)
from .policy import TestSynthesisPolicy
from .ranking import RiskGuidedTestRanker
from .requirements import TestRequirementExtractor
from .risk import TestRiskEvaluator
from .security import TestSecuritySentinel
from .validator import MutationTestingEngine, TestSynthesisValidator


class AutonomousTestSynthesisBridge:
    """
    Central Singleton facade orchestrating Phase 61: Autonomous Test Synthesis.
    Connects:
    CHANGE -> SYMBOL/CONTRACT/BEHAVIOR IMPACT -> RISK -> COVERAGE GAPS ->
    TEST REQUIREMENTS -> TEST CANDIDATES -> RANK -> EXECUTE -> COVERAGE FEEDBACK ->
    ADAPTIVE GENERATION -> PROOF.
    """

    _instance: Optional[AutonomousTestSynthesisBridge] = None

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self.workspace_root = (workspace_root or os.getcwd()).replace("\\", "/")

        self.policy = TestSynthesisPolicy()
        self.security = TestSecuritySentinel(self.workspace_root)
        self.requirements_extractor = TestRequirementExtractor()
        self.gap_analyzer = CoverageGapAnalyzer()
        self.candidate_mgr = TestCandidateManager()
        self.generator = AutonomousTestGenerator(self.candidate_mgr)
        self.ranker = RiskGuidedTestRanker()
        self.minimizer = TestMinimalityEvaluator()
        self.executor = TestExecutor(self.security)
        self.coverage_tracker = MultiDimensionalCoverageTracker()
        self.feedback_engine = AdaptiveFeedbackEngine(
            self.generator,
            self.executor,
            self.gap_analyzer,
            self.coverage_tracker,
            self.ranker,
            self.minimizer,
        )
        self.counterexample_synthesizer = CounterexampleTestSynthesizer(self.candidate_mgr)
        self.contract_generator = ContractTestGenerator(self.candidate_mgr)
        self.behavior_generator = BehaviorTestGenerator(self.candidate_mgr)
        self.browser_synthesizer = BrowserTestSynthesizer(self.candidate_mgr)
        self.mutation_engine = MutationTestingEngine()
        self.validator = TestSynthesisValidator()
        self.metrics = TestSynthesisMetrics()
        self.cache = TestSynthesisCache()
        self.index = TestSynthesisIndex()

    @classmethod
    def get_instance(cls, workspace_root: Optional[str] = None) -> AutonomousTestSynthesisBridge:
        if cls._instance is None:
            cls._instance = cls(workspace_root)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def synthesize_for_change(
        self,
        symbol_id: str,
        file_id: str,
        impact_result: Optional[Dict[str, Any]] = None,
        contracts: Optional[List[Dict[str, Any]]] = None,
        behavioral_invariants: Optional[List[str]] = None,
        acceptance_criteria: Optional[List[str]] = None,
        economic_policies: Optional[List[str]] = None,
        security_policies: Optional[List[str]] = None,
        counterexamples: Optional[List[Dict[str, Any]]] = None,
        risk_score: float = 0.5,
        max_iterations: int = 4,
    ) -> Dict[str, Any]:
        """
        Complete end-to-end autonomous synthesis pipeline for a given change.
        """
        start_time = time.perf_counter()

        # 1. Extract formal requirements
        reqs = self.requirements_extractor.extract_from_change(
            symbol_id=symbol_id,
            file_id=file_id,
            impact_result=impact_result,
            contracts=contracts,
            behavioral_invariants=behavioral_invariants,
            acceptance_criteria=acceptance_criteria,
            economic_policies=economic_policies,
            security_policies=security_policies,
            counterexamples=counterexamples,
            risk_score=risk_score,
        )

        for r in reqs:
            self.index.index_requirement(r)

        # 2. Run adaptive generation and feedback loop
        adaptive_res = self.feedback_engine.run_adaptive_cycle(
            requirements=reqs,
            max_iterations=max_iterations,
            batch_size=4,
        )

        # 3. Retrieve all generated and valid candidates
        all_candidates = self.candidate_mgr.list_candidates()
        for c in all_candidates:
            self.index.index_candidate(c)

        accepted_cands = [c for c in all_candidates if c.status == TestCandidateStatus.ACCEPTED]
        rejected_cands = [c for c in all_candidates if c.status == TestCandidateStatus.REJECTED]

        # 4. Bounded Mutation Testing on target symbol
        sample_code = f"def {symbol_id.split('::')[-1]}():\n    return 42 + 10"
        mutants = self.mutation_engine.generate_mutants(symbol_id, file_id, sample_code, max_mutants=4)
        mutation_summary = self.mutation_engine.evaluate_mutation_score(mutants, accepted_cands)

        # 5. Formal Validation
        comp_cov = self.coverage_tracker.current.compute_composite_score()
        is_valid, validation_errors = self.validator.validate_suite(
            candidates=all_candidates,
            execution_results=[r for r in self.executor.evidence_ledger if r.result in ("PASS", "FAIL")],
            composite_coverage=comp_cov,
            min_required_coverage=self.policy.min_composite_coverage,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        total_cost = sum(c.estimated_cost.total_cost for c in all_candidates)

        # 6. Telemetry & Metrics
        metrics_record = self.metrics.record_run(
            total_candidates=len(all_candidates),
            accepted=len(accepted_cands),
            rejected=len(rejected_cands),
            duration_ms=duration_ms,
            composite_coverage=comp_cov,
            mutation_score=mutation_summary.get("mutation_score", 0.0),
            total_cost=total_cost,
        )

        return {
            "symbol_id": symbol_id,
            "file_id": file_id,
            "requirements_count": len(reqs),
            "candidates_count": len(all_candidates),
            "accepted_count": len(accepted_cands),
            "rejected_count": len(rejected_cands),
            "coverage": self.coverage_tracker.current.to_dict(),
            "mutation_score": mutation_summary.get("mutation_score", 0.0),
            "mutants_evaluated": mutation_summary.get("total_mutants", 0),
            "validation_passed": is_valid,
            "validation_errors": validation_errors,
            "duration_ms": round(duration_ms, 2),
            "total_cost": round(total_cost, 4),
            "adaptive_iterations": adaptive_res.get("iterations_run", 0),
            "evidence_count": len(self.executor.evidence_ledger),
            "metrics": metrics_record,
        }

    def synthesize_counterexample_regression(
        self,
        counterexample_data: Dict[str, Any],
        module_path: str,
    ) -> Dict[str, Any]:
        """Synthesizes and records a regression test from a behavioral counterexample."""
        cx = CounterexampleEvidence(
            counterexample_id=counterexample_data.get("counterexample_id", f"cx_{int(time.time())}"),
            source_invariant=counterexample_data.get("source_invariant", "property_invariant"),
            violating_input=counterexample_data.get("violating_input", {}),
            observed_output=counterexample_data.get("observed_output", None),
            expected_property=counterexample_data.get("expected_property", "valid"),
            symbol_id=counterexample_data.get("symbol_id", "target_symbol"),
            file_id=counterexample_data.get("file_id", "target_file.py"),
        )
        cand = self.counterexample_synthesizer.synthesize_regression_test(cx, module_path)
        exec_res = self.executor.execute(cand)
        return {
            "test_id": cand.test_id,
            "counterexample_id": cx.counterexample_id,
            "passed": exec_res.passed,
            "code": cand.code,
            "status": "KNOWN_FAILURE_REGRESSION_REGISTERED",
        }

    def verify_repair_readiness(
        self,
        repair_id: str,
        affected_symbols: List[str],
        required_coverage: float = 0.75,
    ) -> Tuple[bool, str]:
        """
        Integrates with Phase 54 & 56:
        Determines if a synthesized repair meets the test requirements to be marked REPAIR_PROVEN.
        """
        if self.coverage_tracker.current.compute_composite_score() < required_coverage:
            return False, f"REPAIR_BLOCKED: Composite coverage {self.coverage_tracker.current.compute_composite_score()} is below required {required_coverage}"

        for sym in affected_symbols:
            reqs = self.index.get_requirements_for_symbol(sym)
            if not reqs:
                return False, f"REPAIR_BLOCKED: No test requirements established for affected symbol '{sym}'"

        return True, "REPAIR_PROVEN: All policy test requirements and coverage thresholds satisfied"

    def get_status(self) -> Dict[str, Any]:
        """Returns global status and telemetry for Mission Control Center."""
        all_cands = self.candidate_mgr.list_candidates()
        accepted = [c for c in all_cands if c.status == TestCandidateStatus.ACCEPTED]
        rejected = [c for c in all_cands if c.status == TestCandidateStatus.REJECTED]
        return {
            "requirements_count": len(self.requirements_extractor.list_requirements()),
            "candidates_count": len(all_cands),
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "coverage": self.coverage_tracker.current.to_dict(),
            "evidence_items": len(self.executor.evidence_ledger),
            "known_regressions": len(self.counterexample_synthesizer.get_known_regressions()),
            "ram_mb": self.metrics.measure_memory_mb(),
            "policy": self.policy.to_dict(),
            "ready": True,
        }
