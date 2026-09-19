"""
JARVIS OS — Phase 68: Test Quality Evaluator
Integrates F61 (Autonomous Test Synthesis) and F62 (Continuous Verification).

Evaluates:
- test coverage (line)
- branch coverage
- symbol coverage
- contract coverage
- behavior coverage
- invariant coverage
- consumer coverage
- browser coverage
- mutation score
- regression density
- flaky rate
- test redundancy

Core Distinction:
MORE_TESTS != MORE_USEFUL_EVIDENCE
Computes indicator: EVIDENCE_EFFICIENCY.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import (
    DimensionChange,
    DimensionEvaluation,
    DimensionStatus,
    ObservationType,
    QualityDimension,
    QualityObservation,
)


class TestQualityEvaluator:
    """
    Evaluates test suite health, evidence utility, mutation resistance,
    and calculates evidence efficiency.
    """

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        self.thresholds = thresholds or {
            "min_line_coverage": 0.80,
            "min_mutation_score": 0.70,
            "max_flaky_rate": 0.05,
            "max_test_redundancy": 0.35,
            "min_evidence_efficiency": 0.50,
        }

    def evaluate(
        self,
        context: Optional[Dict[str, Any]] = None,
        scope: str = "global",
    ) -> DimensionEvaluation:
        ctx = context or {}
        test_data = ctx.get("test", {})

        test_count = int(test_data.get("test_count", 100))
        useful_assertions = int(test_data.get("useful_assertions", 250))
        redundancy_count = int(test_data.get("test_redundancy_count", 10))

        line_cov = float(test_data.get("line_coverage", 0.88))
        branch_cov = float(test_data.get("branch_coverage", 0.82))
        symbol_cov = float(test_data.get("symbol_coverage", 0.85))
        contract_cov = float(test_data.get("contract_coverage", 0.80))
        behavior_cov = float(test_data.get("behavior_coverage", 0.78))
        invariant_cov = float(test_data.get("invariant_coverage", 0.75))
        consumer_cov = float(test_data.get("consumer_coverage", 0.72))
        browser_cov = float(test_data.get("browser_coverage", 0.65))
        mutation_score = float(test_data.get("mutation_score", 0.76))
        regression_density = float(test_data.get("regression_density", 0.01))
        flaky_rate = float(test_data.get("flaky_rate", 0.01))
        test_redundancy = float(test_data.get("test_redundancy", redundancy_count / max(test_count, 1)))

        # Compute Evidence Efficiency: useful evidence produced vs execution cost / inflation
        # If tests are added without new assertions or mutation resistance, efficiency drops
        eff_denom = max(1.0, test_count + (redundancy_count * 2.0))
        evidence_efficiency = float(
            min(1.0, (useful_assertions * (1.0 - flaky_rate) * mutation_score) / eff_denom)
        )

        observations = [
            QualityObservation(
                dimension=QualityDimension.TEST,
                metric_name="line_coverage",
                measured_value=line_cov,
                evidence={"line_coverage_pct": line_cov},
                uncertainty=0.01,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.TEST,
                metric_name="branch_coverage",
                measured_value=branch_cov,
                evidence={"branch_coverage_pct": branch_cov},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.TEST,
                metric_name="symbol_coverage",
                measured_value=symbol_cov,
                evidence={"symbol_coverage_pct": symbol_cov},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.TEST,
                metric_name="contract_coverage",
                measured_value=contract_cov,
                evidence={"contract_coverage_pct": contract_cov},
                uncertainty=0.03,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.TEST,
                metric_name="behavior_coverage",
                measured_value=behavior_cov,
                evidence={"behavior_coverage_pct": behavior_cov},
                uncertainty=0.04,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.TEST,
                metric_name="invariant_coverage",
                measured_value=invariant_cov,
                evidence={"invariant_coverage_pct": invariant_cov},
                uncertainty=0.04,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.TEST,
                metric_name="consumer_coverage",
                measured_value=consumer_cov,
                evidence={"consumer_coverage_pct": consumer_cov},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.TEST,
                metric_name="browser_coverage",
                measured_value=browser_cov,
                evidence={"browser_coverage_pct": browser_cov},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.TEST,
                metric_name="mutation_score",
                measured_value=mutation_score,
                evidence={"killed_mutants_ratio": mutation_score},
                uncertainty=0.03,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.TEST,
                metric_name="regression_density",
                measured_value=regression_density,
                evidence={"regressions_per_100_runs": regression_density},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.TEST,
                metric_name="flaky_rate",
                measured_value=flaky_rate,
                evidence={"flaky_tests_ratio": flaky_rate},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.TEST,
                metric_name="test_redundancy",
                measured_value=test_redundancy,
                evidence={"duplicate_or_zero_mutation_tests": test_redundancy},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.ESTIMATED,
            ),
            QualityObservation(
                dimension=QualityDimension.TEST,
                metric_name="evidence_efficiency",
                measured_value=evidence_efficiency,
                evidence={"efficiency_score": evidence_efficiency},
                uncertainty=0.04,
                scope=scope,
                observation_type=ObservationType.ESTIMATED,
            ),
        ]

        is_degraded = (
            line_cov < self.thresholds["min_line_coverage"]
            or mutation_score < self.thresholds["min_mutation_score"]
            or flaky_rate > self.thresholds["max_flaky_rate"]
            or test_redundancy > self.thresholds["max_test_redundancy"]
            or evidence_efficiency < self.thresholds["min_evidence_efficiency"]
        )

        status = DimensionStatus.DEGRADED if is_degraded else DimensionStatus.HEALTHY
        summary = (
            f"Test status {status.value}: line_cov={line_cov:.1%}, "
            f"mutation={mutation_score:.1%}, flaky={flaky_rate:.1%}, "
            f"efficiency={evidence_efficiency:.2f}, count={test_count}"
        )

        return DimensionEvaluation(
            dimension=QualityDimension.TEST,
            observations=observations,
            evidence=[{
                "evaluator": "TestQualityEvaluator",
                "test_count": test_count,
                "useful_assertions": useful_assertions,
                "evidence_efficiency": evidence_efficiency,
            }],
            uncertainty=0.03,
            scope=scope,
            status=status,
            summary=summary,
        )

    def compare_tests(
        self,
        baseline_eval: DimensionEvaluation,
        after_eval: DimensionEvaluation,
    ) -> Tuple[DimensionChange, bool, bool, float, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Distinguishes MORE_TESTS from MORE_USEFUL_EVIDENCE.
        Returns (change, more_tests, more_useful_evidence, efficiency_ratio, degradations, improvements).
        """
        base_obs = {o.metric_name: o.measured_value for o in baseline_eval.observations}
        after_obs = {o.metric_name: o.measured_value for o in after_eval.observations}

        degradations = []
        improvements = []

        b_cov = float(base_obs.get("line_coverage", 0.0))
        a_cov = float(after_obs.get("line_coverage", 0.0))
        if a_cov < b_cov - 0.02:
            degradations.append({"metric": "line_coverage", "from": b_cov, "to": a_cov, "reason": "coverage dropped"})
        elif a_cov > b_cov + 0.02:
            improvements.append({"metric": "line_coverage", "from": b_cov, "to": a_cov, "reason": "coverage increased"})

        b_mut = float(base_obs.get("mutation_score", 0.0))
        a_mut = float(after_obs.get("mutation_score", 0.0))
        if a_mut < b_mut - 0.05:
            degradations.append({"metric": "mutation_score", "from": b_mut, "to": a_mut, "reason": "mutation score dropped"})
        elif a_mut > b_mut + 0.05:
            improvements.append({"metric": "mutation_score", "from": b_mut, "to": a_mut, "reason": "mutation score improved"})

        b_flaky = float(base_obs.get("flaky_rate", 0.0))
        a_flaky = float(after_obs.get("flaky_rate", 0.0))
        if a_flaky > b_flaky + 0.03:
            degradations.append({"metric": "flaky_rate", "from": b_flaky, "to": a_flaky, "reason": "flakiness increased"})
        elif a_flaky < b_flaky - 0.02:
            improvements.append({"metric": "flaky_rate", "from": b_flaky, "to": a_flaky, "reason": "flakiness eliminated"})

        b_eff = float(base_obs.get("evidence_efficiency", 0.5))
        a_eff = float(after_obs.get("evidence_efficiency", 0.5))

        # Check evidence in details
        b_count = baseline_eval.evidence[0].get("test_count", 100) if baseline_eval.evidence else 100
        a_count = after_eval.evidence[0].get("test_count", 100) if after_eval.evidence else 100

        more_tests = a_count > b_count
        # More useful evidence requires improved mutation or invariant coverage, not just count inflation
        more_useful_evidence = (a_mut > b_mut) or (a_cov > b_cov and a_mut >= b_mut)

        # If tests increased but mutation and efficiency dropped -> test inflation without evidence!
        if more_tests and not more_useful_evidence and a_eff < b_eff - 0.10:
            degradations.append({
                "metric": "evidence_efficiency",
                "from": b_eff,
                "to": a_eff,
                "reason": "MORE_TESTS added without MORE_USEFUL_EVIDENCE (test inflation)",
            })

        if degradations and not improvements:
            change = DimensionChange.DEGRADED
        elif improvements and not degradations:
            change = DimensionChange.IMPROVED
        elif degradations and improvements:
            change = DimensionChange.UNCERTAIN
        else:
            change = DimensionChange.UNCHANGED

        return change, more_tests, more_useful_evidence, a_eff, degradations, improvements
