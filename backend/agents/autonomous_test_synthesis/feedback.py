"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: feedback.py
Adaptive generation loop: GENERATE -> EXECUTE -> OBSERVE -> UPDATE COVERAGE -> UPDATE RISK -> GENERATE NEXT.
Recalculates remaining gaps and adjusts priorities after every batch.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .analyzer import CoverageGapAnalyzer
from .candidate import TestCandidateManager
from .coverage import MultiDimensionalCoverageTracker
from .executor import TestExecutor
from .generator import AutonomousTestGenerator
from .minimizer import TestMinimalityEvaluator
from .models import (
    TestCandidate,
    TestCandidateStatus,
    TestExecutionResult,
    TestRequirement,
)
from .ranking import RiskGuidedTestRanker


class AdaptiveFeedbackEngine:
    """
    Drives iterative, budget-aware test synthesis until coverage requirements are met
    or maximum iterations are exhausted.
    """

    def __init__(
        self,
        generator: AutonomousTestGenerator,
        executor: TestExecutor,
        gap_analyzer: CoverageGapAnalyzer,
        coverage_tracker: MultiDimensionalCoverageTracker,
        ranker: RiskGuidedTestRanker,
        minimizer: TestMinimalityEvaluator,
    ) -> None:
        self.generator = generator
        self.executor = executor
        self.gap_analyzer = gap_analyzer
        self.coverage_tracker = coverage_tracker
        self.ranker = ranker
        self.minimizer = minimizer

        self.iteration_history: List[Dict[str, Any]] = []
        self.failure_history: Dict[str, int] = {}

    def run_adaptive_cycle(
        self,
        requirements: List[TestRequirement],
        max_iterations: int = 5,
        batch_size: int = 4,
    ) -> Dict[str, Any]:
        """Execute the adaptive generation and feedback loop."""
        iteration = 0
        total_executed = 0
        all_results: List[TestExecutionResult] = []

        while iteration < max_iterations:
            iteration += 1

            # 1. Analyze remaining coverage gaps
            gaps = self.gap_analyzer.analyze_gaps(requirements)
            if not gaps:
                break

            # 2. Generate candidates for highest priority gaps
            raw_candidates: List[TestCandidate] = []
            for gap in gaps[:batch_size]:
                req_id = gap["requirement_id"]
                req = next((r for r in requirements if r.requirement_id == req_id), None)
                if req:
                    cands = self.generator.generate_for_requirement(req)
                    raw_candidates.extend(cands)

            if not raw_candidates:
                break

            # 3. Minimize & Quality Filter
            valid_candidates = self.minimizer.filter_minimal_set(raw_candidates)

            # 4. Risk-Guided Ranking
            ranked_candidates = self.ranker.rank_candidates(
                valid_candidates, failure_history=self.failure_history
            )

            # 5. Execute top batch
            batch_to_run = ranked_candidates[:batch_size]
            for cand in batch_to_run:
                cand.status = TestCandidateStatus.EXECUTING

            exec_results = self.executor.execute_batch(batch_to_run)
            total_executed += len(exec_results)
            all_results.extend(exec_results)

            # 6. Observe & Update Feedback
            for cand, res in zip(batch_to_run, exec_results):
                cand.status = TestCandidateStatus.ACCEPTED if res.passed else TestCandidateStatus.REJECTED
                if not res.passed:
                    self.failure_history[cand.target] = self.failure_history.get(cand.target, 0) + 1

                # Update multi-dimensional coverage tracker
                req = next((r for r in requirements if r.requirement_id == cand.requirement_id), None)
                sc_type = req.scenario_type if req else "unit"
                self.coverage_tracker.update_with_result(res, scenario_type=sc_type)

                # Record gap satisfaction in analyzer
                if res.passed:
                    self.gap_analyzer.record_test_execution(
                        symbol_id=req.symbol_id if req else None,
                        contract_id=req.contract_id if req else None,
                        consumer_id=req.consumer_id if req else None,
                        invariant=req.invariant if req else None,
                    )

            # Record iteration telemetry
            cov_metrics = self.coverage_tracker.current
            iter_info = {
                "iteration": iteration,
                "gaps_count": len(gaps),
                "candidates_generated": len(raw_candidates),
                "candidates_accepted": len([r for r in exec_results if r.passed]),
                "composite_coverage": cov_metrics.compute_composite_score(),
            }
            self.iteration_history.append(iter_info)

            # Stop early if composite coverage targets are satisfied
            if self.coverage_tracker.is_sufficient(min_composite=0.80):
                break

        return {
            "iterations_run": iteration,
            "total_executed": total_executed,
            "results": [r.to_dict() for r in all_results],
            "final_coverage": self.coverage_tracker.current.to_dict(),
            "history": self.iteration_history,
        }
