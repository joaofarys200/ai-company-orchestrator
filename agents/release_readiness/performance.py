"""
Performance Readiness Module
Phase 70 — Autonomous Release Readiness & Production Governance

Compares baseline vs candidate performance across 7 physical and simulated dimensions.
Strictly distinguishes observed from estimated and inferred measurements.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import PerformanceClassification, MetricNature, BlockerCategory, ReleaseBlocker


class PerformanceReadinessEvaluator:
    """Evaluates latency, throughput, compute budgets, and browser performance."""

    @classmethod
    def evaluate(
        cls,
        baseline_metrics: Dict[str, Any],
        current_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compares BASELINE vs CURRENT across:
        - latency (ms)
        - throughput (rps)
        - CPU (%)
        - memory (MB)
        - I/O (MB/s or ops)
        - startup (ms)
        - browser performance (ms / frame drops)
        Classifications: IMPROVED, WITHIN_BUDGET, DEGRADED, CRITICAL_DEGRADATION, UNKNOWN
        Distinguishes: observed, estimated, inferred
        """
        if not current_metrics or not baseline_metrics:
            return {
                "classification": PerformanceClassification.UNKNOWN,
                "nature": MetricNature.INFERRED.value,
                "blockers": [
                    ReleaseBlocker(
                        blocker_id="blocker-perf-missing-metrics",
                        category=BlockerCategory.MISSING_MANDATORY_EVIDENCE,
                        description="Performance metrics missing or incomplete",
                        evidence="Unable to compare current performance against established baseline."
                    )
                ],
                "requires_human_review": True,
                "review_reasons": ["Performance metrics missing"]
            }

        nature_str = current_metrics.get("nature", MetricNature.OBSERVED.value)
        try:
            nature = MetricNature(nature_str)
        except ValueError:
            nature = MetricNature.ESTIMATED

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []
        dimension_deltas: Dict[str, Dict[str, Any]] = {}

        dimensions = [
            ("latency_p95_ms", "lower", 0.50, 0.20),      # metric, better_dir, crit_pct, warn_pct
            ("throughput_rps", "higher", 0.35, 0.15),
            ("cpu_utilization_pct", "lower", 0.60, 0.25),
            ("memory_mb", "lower", 0.50, 0.20),
            ("io_read_mb_s", "lower", 0.80, 0.30),
            ("startup_ms", "lower", 0.75, 0.30),
            ("browser_render_ms", "lower", 0.60, 0.25)
        ]

        any_critical = False
        any_degraded = False
        all_improved_or_equal = True

        for metric_name, direction, crit_threshold, warn_threshold in dimensions:
            base_val = float(baseline_metrics.get(metric_name, 0.0))
            curr_val = float(current_metrics.get(metric_name, 0.0))

            if base_val <= 0.0 and curr_val <= 0.0:
                continue

            delta_abs = curr_val - base_val
            pct_change = (delta_abs / base_val) if base_val > 0 else 0.0

            is_degradation = False
            is_critical = False
            is_improvement = False

            if direction == "lower":
                # Lower is better; positive pct_change is degradation
                if pct_change > crit_threshold:
                    is_critical = True
                elif pct_change > warn_threshold:
                    is_degradation = True
                elif pct_change < -0.05:
                    is_improvement = True
            else:
                # Higher is better; negative pct_change is degradation
                if pct_change < -crit_threshold:
                    is_critical = True
                elif pct_change < -warn_threshold:
                    is_degradation = True
                elif pct_change > 0.05:
                    is_improvement = True

            dimension_deltas[metric_name] = {
                "baseline": base_val,
                "current": curr_val,
                "pct_change": round(pct_change * 100, 2),
                "nature": nature.value,
                "status": "CRITICAL" if is_critical else ("DEGRADED" if is_degradation else ("IMPROVED" if is_improvement else "WITHIN_BUDGET"))
            }

            if is_critical:
                any_critical = True
                all_improved_or_equal = False
                blockers.append(ReleaseBlocker(
                    blocker_id=f"blocker-perf-{metric_name}",
                    category=BlockerCategory.SEVERE_PERFORMANCE_REGRESSION,
                    description=f"Critical performance regression in {metric_name}: {pct_change*100:.1f}% shift",
                    evidence=f"Baseline: {base_val}, Current: {curr_val}. Exceeds critical budget ({crit_threshold*100:.0f}%)."
                ))
            elif is_degradation:
                any_degraded = True
                all_improved_or_equal = False
                requires_human_review = True
                review_reasons.append(f"Performance degradation in {metric_name} ({pct_change*100:.1f}%)")
            elif not is_improvement:
                # neutral / within budget
                pass

        if nature != MetricNature.OBSERVED:
            # If metrics are estimated or inferred, flag human review requirement
            requires_human_review = True
            review_reasons.append(f"Performance evaluation relies on {nature.value.upper()} metrics rather than observed measurements")

        classification = PerformanceClassification.WITHIN_BUDGET
        if any_critical:
            classification = PerformanceClassification.CRITICAL_DEGRADATION
        elif any_degraded:
            classification = PerformanceClassification.DEGRADED
        elif all_improved_or_equal and len(dimension_deltas) > 0:
            classification = PerformanceClassification.IMPROVED

        return {
            "classification": classification,
            "nature": nature.value,
            "dimension_deltas": dimension_deltas,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons
        }
