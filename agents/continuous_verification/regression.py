"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: regression.py
RegressionComparator performing multidimensional evaluation (11 dimensions) between CURRENT and BASELINE.
Invariant: Never classify a change merely on "pytest exit code 0".
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import (
    BaselineSnapshot,
    CoverageVector,
    RegressionClassification,
    RegressionComparisonResult,
)


class RegressionComparator:
    """
    Compares CURRENT run vs BASELINE snapshot across 11 dimensions:
    1. pass/fail
    2. line coverage
    3. branch coverage
    4. symbol coverage
    5. contract coverage
    6. behavior coverage
    7. invariant coverage
    8. consumer coverage
    9. browser coverage
    10. mutation coverage
    11. execution time
    """

    def compare(
        self,
        current_results: Dict[str, str],  # test_id -> "PASS" / "FAIL"
        current_coverage: CoverageVector,
        current_duration: float,
        baseline: Optional[BaselineSnapshot] = None,
        flaky_tests: Optional[List[str]] = None,
        is_environmental_error: bool = False,
    ) -> RegressionComparisonResult:
        """Evaluate multidimensional regression status."""
        dims: Dict[str, Dict[str, Any]] = {}
        regressed_items: List[str] = []
        improved_items: List[str] = []

        if is_environmental_error:
            return RegressionComparisonResult(
                classification=RegressionClassification.ENVIRONMENTAL_FAILURE,
                dimensions_evaluated={"environment": {"status": "FAILED", "reason": "Host/environment fault"}},
                regressed_items=["environment"],
                explanation="Environmental failure detected during verification execution",
                confidence=0.9,
            )

        if flaky_tests:
            return RegressionComparisonResult(
                classification=RegressionClassification.FLAKY_SIGNAL,
                dimensions_evaluated={"flaky": {"flaky_tests": flaky_tests}},
                regressed_items=flaky_tests,
                explanation=f"Flaky signal detected on tests: {flaky_tests}",
                confidence=0.85,
            )

        # Baseline coverage dictionary
        b_cov = baseline.coverage_vector if baseline else CoverageVector()
        b_results = baseline.test_results if baseline else {}
        b_dur = baseline.execution_duration if baseline else 0.0

        # Dimension 1: Pass/Fail
        failed_tests = [t for t, s in current_results.items() if s in ("FAIL", "ERROR")]
        if failed_tests:
            regressed_items.extend([f"failed_test:{t}" for t in failed_tests])
            dims["pass_fail"] = {"status": "REGRESSED", "failed_tests": failed_tests}
        else:
            dims["pass_fail"] = {"status": "PASSED", "passed_count": len(current_results)}

        # Coverage Dimensions 2-10
        cov_dimensions = [
            ("line_coverage", current_coverage.line_coverage, b_cov.line_coverage),
            ("branch_coverage", current_coverage.branch_coverage, b_cov.branch_coverage),
            ("symbol_coverage", current_coverage.symbol_coverage, b_cov.symbol_coverage),
            ("contract_coverage", current_coverage.contract_coverage, b_cov.contract_coverage),
            ("behavior_coverage", current_coverage.behavior_coverage, b_cov.behavior_coverage),
            ("invariant_coverage", current_coverage.invariant_coverage, b_cov.invariant_coverage),
            ("consumer_coverage", current_coverage.consumer_coverage, b_cov.consumer_coverage),
            ("browser_coverage", current_coverage.browser_coverage, b_cov.browser_coverage),
            ("mutation_coverage", current_coverage.mutation_coverage, b_cov.mutation_coverage),
        ]

        for dim_name, c_val, b_val in cov_dimensions:
            delta = round(c_val - b_val, 4)
            if delta < -0.05:  # Noticeable regression in coverage
                regressed_items.append(f"coverage_drop:{dim_name}")
                dims[dim_name] = {"status": "REGRESSED", "current": c_val, "baseline": b_val, "delta": delta}
            elif delta > 0.05:
                improved_items.append(f"coverage_gain:{dim_name}")
                dims[dim_name] = {"status": "IMPROVED", "current": c_val, "baseline": b_val, "delta": delta}
            else:
                dims[dim_name] = {"status": "MAINTAINED", "current": c_val, "baseline": b_val, "delta": delta}

        # Dimension 11: Execution Time
        if b_dur > 0 and current_duration > (b_dur * 3.5) and current_duration > 5.0:
            regressed_items.append("performance_drop:execution_time")
            dims["execution_time"] = {"status": "REGRESSED", "current_s": current_duration, "baseline_s": b_dur}
        elif b_dur > 0 and current_duration < (b_dur * 0.7):
            improved_items.append("performance_gain:execution_time")
            dims["execution_time"] = {"status": "IMPROVED", "current_s": current_duration, "baseline_s": b_dur}
        else:
            dims["execution_time"] = {"status": "STABLE", "current_s": current_duration, "baseline_s": b_dur}

        # Final Classification
        if regressed_items:
            classification = RegressionClassification.REGRESSION
            explanation = f"Regressions detected across {len(regressed_items)} dimension(s): {', '.join(regressed_items[:3])}"
        elif improved_items and not failed_tests:
            classification = RegressionClassification.IMPROVEMENT
            explanation = f"Improvements observed in {len(improved_items)} dimension(s)"
        elif not current_results:
            classification = RegressionClassification.INSUFFICIENT_EVIDENCE
            explanation = "No tests were executed; cannot classify regression status"
        else:
            classification = RegressionClassification.NO_REGRESSION
            explanation = "All 11 dimensions evaluated cleanly against baseline with no regressions"

        return RegressionComparisonResult(
            classification=classification,
            dimensions_evaluated=dims,
            regressed_items=regressed_items,
            improved_items=improved_items,
            explanation=explanation,
            confidence=1.0 if baseline else 0.85,
        )
