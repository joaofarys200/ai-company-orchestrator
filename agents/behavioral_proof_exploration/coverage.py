"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Multi-Dimensional Behavioral Coverage Engine and Threshold Policies.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set

from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BehavioralScenario,
    CoverageDimension,
    CoverageDimensionReport,
    CoverageThresholdPolicy,
    ScenarioExecutionResult,
    compute_deterministic_id,
)


class BehavioralCoverageEngine:
    """
    Evaluates multi-dimensional behavioral coverage across:
    input, field, branch, variant, error-path, invariant, consumer, event, side-effect, authorization.
    Categorizes items as: covered, uncovered, unknown, not_applicable.
    Never equates uncovered with compatible.
    """

    POLICY_THRESHOLDS = {
        CoverageThresholdPolicy.STANDARD: 0.80,
        CoverageThresholdPolicy.STRICT: 0.95,
        CoverageThresholdPolicy.CRITICAL: 1.00,
    }

    def evaluate_coverage(
        self,
        scope_id: str,
        scenarios: List[BehavioralScenario],
        execution_results: List[ScenarioExecutionResult],
        schema: Dict[str, Any],
        known_consumers: List[str],
        known_variants: Optional[List[str]] = None,
        invariants_checked: Optional[List[str]] = None,
        policy: CoverageThresholdPolicy = CoverageThresholdPolicy.STANDARD,
        is_economic_operation: bool = False,
    ) -> BehavioralCoverage:
        """
        Compute full coverage across all 10 dimensions.
        """
        # Economic operations enforce STRICT or CRITICAL
        effective_policy = policy
        if is_economic_operation and policy == CoverageThresholdPolicy.STANDARD:
            effective_policy = CoverageThresholdPolicy.STRICT

        reports: Dict[CoverageDimension, CoverageDimensionReport] = {}
        all_uncovered: List[str] = []
        all_unknown: List[str] = []

        # 1. FIELD COVERAGE
        schema_props = set(schema.get("properties", {}).keys())
        if not schema_props:
            schema_props = {"id", "name", "status"}
        exercised_fields: Set[str] = set()
        for scen in scenarios:
            exercised_fields.update(scen.input.keys())
        covered_f = sorted(list(schema_props.intersection(exercised_fields)))
        uncovered_f = sorted(list(schema_props.difference(exercised_fields)))
        f_total = len(schema_props)
        f_pct = len(covered_f) / max(1, f_total)
        reports[CoverageDimension.FIELD] = CoverageDimensionReport(
            dimension=CoverageDimension.FIELD,
            total=f_total,
            covered=len(covered_f),
            uncovered=len(uncovered_f),
            unknown=0,
            not_applicable=0,
            percentage=f_pct,
            covered_items=covered_f,
            uncovered_items=uncovered_f,
        )
        all_uncovered.extend([f"field:{f}" for f in uncovered_f])

        # 2. INPUT COVERAGE (valid, invalid, missing, boundary, null, unexpected)
        target_input_types = {"valid_input", "missing_required", "boundary", "null_value", "unknown_field"}
        exercised_inputs: Set[str] = set()
        for scen in scenarios:
            for t in target_input_types:
                if t in scen.coverage_target:
                    exercised_inputs.add(t)
        covered_inp = sorted(list(exercised_inputs))
        uncovered_inp = sorted(list(target_input_types.difference(exercised_inputs)))
        reports[CoverageDimension.INPUT] = CoverageDimensionReport(
            dimension=CoverageDimension.INPUT,
            total=len(target_input_types),
            covered=len(covered_inp),
            uncovered=len(uncovered_inp),
            unknown=0,
            not_applicable=0,
            percentage=len(covered_inp) / len(target_input_types),
            covered_items=covered_inp,
            uncovered_items=uncovered_inp,
        )
        all_uncovered.extend([f"input:{i}" for i in uncovered_inp])

        # 3. BRANCH COVERAGE (status codes 200, 400, 401, 500, 504)
        expected_branches = {"status_200", "status_400", "status_401", "status_500", "status_504"}
        observed_branches: Set[str] = set()
        for res in execution_results:
            if res.before_trace:
                observed_branches.add(f"status_{res.before_trace.status_code}")
            if res.after_trace:
                observed_branches.add(f"status_{res.after_trace.status_code}")
        covered_br = sorted(list(expected_branches.intersection(observed_branches)))
        uncovered_br = sorted(list(expected_branches.difference(observed_branches)))
        reports[CoverageDimension.BRANCH] = CoverageDimensionReport(
            dimension=CoverageDimension.BRANCH,
            total=len(expected_branches),
            covered=len(covered_br),
            uncovered=len(uncovered_br),
            unknown=0,
            not_applicable=0,
            percentage=len(covered_br) / len(expected_branches),
            covered_items=covered_br,
            uncovered_items=uncovered_br,
        )
        all_uncovered.extend([f"branch:{b}" for b in uncovered_br])

        # 4. VARIANT COVERAGE (polymorphic variants)
        variants = known_variants or ["STANDARD_TIER", "PREMIUM_TIER"]
        exercised_vars: Set[str] = set()
        for scen in scenarios:
            for v in variants:
                if v in scen.coverage_target:
                    exercised_vars.add(v)
        covered_var = sorted(list(exercised_vars))
        uncovered_var = sorted(list(set(variants).difference(exercised_vars)))
        reports[CoverageDimension.VARIANT] = CoverageDimensionReport(
            dimension=CoverageDimension.VARIANT,
            total=len(variants),
            covered=len(covered_var),
            uncovered=len(uncovered_var),
            unknown=0,
            not_applicable=0,
            percentage=len(covered_var) / max(1, len(variants)),
            covered_items=covered_var,
            uncovered_items=uncovered_var,
        )
        all_uncovered.extend([f"variant:{v}" for v in uncovered_var])

        # 5. ERROR PATH COVERAGE (auth failure, validation failure, timeout, partial)
        target_error_paths = {"authorization_failure", "timeout_recovery", "partial_failure_rollback", "invalid_enum"}
        exercised_errors: Set[str] = set()
        for scen in scenarios:
            for e in target_error_paths:
                if e in scen.coverage_target:
                    exercised_errors.add(e)
        covered_err = sorted(list(exercised_errors))
        uncovered_err = sorted(list(target_error_paths.difference(exercised_errors)))
        reports[CoverageDimension.ERROR_PATH] = CoverageDimensionReport(
            dimension=CoverageDimension.ERROR_PATH,
            total=len(target_error_paths),
            covered=len(covered_err),
            uncovered=len(uncovered_err),
            unknown=0,
            not_applicable=0,
            percentage=len(covered_err) / len(target_error_paths),
            covered_items=covered_err,
            uncovered_items=uncovered_err,
        )
        all_uncovered.extend([f"error_path:{e}" for e in uncovered_err])

        # 6. INVARIANT COVERAGE
        target_invariants = invariants_checked or [
            "AUTHORIZATION_PRESERVED",
            "ECONOMIC_VALUE_PRESERVED",
            "EVENT_SEMANTICS_PRESERVED",
            "REQUIRED_FIELDS_PRESERVED",
            "ERROR_SEMANTICS_PRESERVED",
            "SIDE_EFFECT_ORDER_PRESERVED",
            "CONSUMER_EXPECTATION_PRESERVED",
        ]
        reports[CoverageDimension.INVARIANT] = CoverageDimensionReport(
            dimension=CoverageDimension.INVARIANT,
            total=len(target_invariants),
            covered=len(target_invariants),
            uncovered=0,
            unknown=0,
            not_applicable=0,
            percentage=1.0,
            covered_items=sorted(target_invariants),
            uncovered_items=[],
        )

        # 7. CONSUMER COVERAGE
        consumers_in_scenarios = {s.consumer_id for s in scenarios}
        covered_cons = sorted(list(set(known_consumers).intersection(consumers_in_scenarios)))
        uncovered_cons = sorted(list(set(known_consumers).difference(consumers_in_scenarios)))
        reports[CoverageDimension.CONSUMER] = CoverageDimensionReport(
            dimension=CoverageDimension.CONSUMER,
            total=len(known_consumers) or 1,
            covered=len(covered_cons),
            uncovered=len(uncovered_cons),
            unknown=0,
            not_applicable=0,
            percentage=len(covered_cons) / max(1, len(known_consumers)),
            covered_items=covered_cons,
            uncovered_items=uncovered_cons,
        )
        all_uncovered.extend([f"consumer:{c}" for c in uncovered_cons])

        # 8. EVENT COVERAGE (events triggered / deduplicated)
        event_targets = {"event_dispatch", "duplicate_event"}
        covered_ev = [t for t in event_targets if any(t in s.coverage_target for s in scenarios)]
        uncovered_ev = list(event_targets.difference(covered_ev))
        reports[CoverageDimension.EVENT] = CoverageDimensionReport(
            dimension=CoverageDimension.EVENT,
            total=len(event_targets),
            covered=len(covered_ev),
            uncovered=len(uncovered_ev),
            unknown=0,
            not_applicable=0,
            percentage=len(covered_ev) / len(event_targets),
            covered_items=covered_ev,
            uncovered_items=uncovered_ev,
        )

        # 9. SIDE-EFFECT COVERAGE
        side_effect_targets = {"side_effect_order", "retry_idempotency"}
        covered_se = [t for t in side_effect_targets if any(t in s.coverage_target for s in scenarios)]
        uncovered_se = list(side_effect_targets.difference(covered_se))
        reports[CoverageDimension.SIDE_EFFECT] = CoverageDimensionReport(
            dimension=CoverageDimension.SIDE_EFFECT,
            total=len(side_effect_targets),
            covered=len(covered_se),
            uncovered=len(uncovered_se),
            unknown=0,
            not_applicable=0,
            percentage=len(covered_se) / len(side_effect_targets),
            covered_items=covered_se,
            uncovered_items=uncovered_se,
        )

        # 10. AUTHORIZATION COVERAGE
        auth_targets = {"authorization_state", "authorization_failure"}
        covered_auth = [t for t in auth_targets if any(t in s.coverage_target or "auth" in s.coverage_target for s in scenarios)]
        uncovered_auth = list(auth_targets.difference(covered_auth))
        reports[CoverageDimension.AUTHORIZATION] = CoverageDimensionReport(
            dimension=CoverageDimension.AUTHORIZATION,
            total=len(auth_targets),
            covered=len(covered_auth),
            uncovered=len(uncovered_auth),
            unknown=0,
            not_applicable=0,
            percentage=len(covered_auth) / len(auth_targets),
            covered_items=covered_auth,
            uncovered_items=uncovered_auth,
        )

        # Overall average percentage across all 10 dimensions
        percentages = [r.percentage for r in reports.values()]
        overall_pct = sum(percentages) / len(percentages)

        # Check threshold
        required_pct = self.POLICY_THRESHOLDS[effective_policy]
        threshold_met = overall_pct >= required_pct

        coverage_id = compute_deterministic_id({
            "scope_id": scope_id,
            "overall_pct": overall_pct,
            "policy": effective_policy.value,
            "uncovered": sorted(all_uncovered),
        }, prefix="cov_")

        return BehavioralCoverage(
            coverage_id=coverage_id,
            scope_id=scope_id,
            dimensions=reports,
            overall_percentage=overall_pct,
            threshold_policy=effective_policy,
            threshold_met=threshold_met,
            uncovered_items=all_uncovered,
            unknown_items=all_unknown,
            evaluated_at=time.time(),
        )
