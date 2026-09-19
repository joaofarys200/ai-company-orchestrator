"""
JARVIS OS — Phase 68: Quality Regression Detector & Snapshot Comparison
Compares QUALITY_BASELINE vs QUALITY_AFTER across all 9 dimensions.

Detects:
- architecture degradation
- test evidence degradation
- contract degradation
- behavior degradation
- security degradation
- reliability degradation
- maintainability degradation

Classifications:
- CRITICAL
- SIGNIFICANT
- MINOR
- UNCERTAIN

Core Invariant:
Never declare a regression when the observed difference lies within measurement uncertainty.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .architecture_quality import ArchitectureQualityEvaluator
from .behavior_quality import BehaviorQualityEvaluator
from .code_quality import CodeQualityEvaluator
from .contract_quality import ContractQualityEvaluator
from .maintainability import MaintainabilityQualityEvaluator
from .models import (
    DimensionChange,
    QualityDelta,
    QualityRegressionLevel,
    QualitySnapshot,
)
from .performance_quality import PerformanceQualityEvaluator
from .reliability_quality import ReliabilityQualityEvaluator
from .security_quality import SecurityQualityEvaluator
from .test_quality import TestQualityEvaluator


class QualityRegressionDetector:
    """
    Performs rigorous before/after comparison between snapshots, enforcing uncertainty bands.
    """

    def __init__(self) -> None:
        self.arch_eval = ArchitectureQualityEvaluator()
        self.code_eval = CodeQualityEvaluator()
        self.test_eval = TestQualityEvaluator()
        self.contract_eval = ContractQualityEvaluator()
        self.behavior_eval = BehaviorQualityEvaluator()
        self.sec_eval = SecurityQualityEvaluator()
        self.perf_eval = PerformanceQualityEvaluator()
        self.rel_eval = ReliabilityQualityEvaluator()
        self.maint_eval = MaintainabilityQualityEvaluator()

    def compare_snapshots(
        self,
        baseline: QualitySnapshot,
        after: QualitySnapshot,
    ) -> QualityDelta:
        dimension_changes: Dict[str, DimensionChange] = {}
        all_degradations: List[Dict[str, Any]] = []
        all_improvements: List[Dict[str, Any]] = []

        # 1. Architecture
        b_arch = baseline.dimensions.get("ARCHITECTURE")
        a_arch = after.dimensions.get("ARCHITECTURE")
        if b_arch and a_arch:
            ch, deg, imp = self.arch_eval.compare_architecture(b_arch, a_arch)
            dimension_changes["ARCHITECTURE"] = ch
            all_degradations.extend(deg)
            all_improvements.extend(imp)

        # 2. Code
        b_code = baseline.dimensions.get("CODE")
        a_code = after.dimensions.get("CODE")
        if b_code and a_code:
            ch, deg, imp = self.code_eval.compare_code(b_code, a_code)
            dimension_changes["CODE"] = ch
            all_degradations.extend(deg)
            all_improvements.extend(imp)

        # 3. Test
        b_test = baseline.dimensions.get("TEST")
        a_test = after.dimensions.get("TEST")
        more_tests = False
        more_useful_evidence = False
        eff = 1.0
        if b_test and a_test:
            ch, more_tests, more_useful_evidence, eff, deg, imp = self.test_eval.compare_tests(b_test, a_test)
            dimension_changes["TEST"] = ch
            all_degradations.extend(deg)
            all_improvements.extend(imp)

        # 4. Contract
        b_cont = baseline.dimensions.get("CONTRACT")
        a_cont = after.dimensions.get("CONTRACT")
        if b_cont and a_cont:
            ch, deg, imp = self.contract_eval.compare_contracts(b_cont, a_cont)
            dimension_changes["CONTRACT"] = ch
            all_degradations.extend(deg)
            all_improvements.extend(imp)

        # 5. Behavior
        b_beh = baseline.dimensions.get("BEHAVIOR")
        a_beh = after.dimensions.get("BEHAVIOR")
        if b_beh and a_beh:
            ch, deg, imp = self.behavior_eval.compare_behavior(b_beh, a_beh)
            dimension_changes["BEHAVIOR"] = ch
            all_degradations.extend(deg)
            all_improvements.extend(imp)

        # 6. Security
        b_sec = baseline.dimensions.get("SECURITY")
        a_sec = after.dimensions.get("SECURITY")
        if b_sec and a_sec:
            ch, is_crit_blocked, deg, imp = self.sec_eval.compare_security(b_sec, a_sec)
            dimension_changes["SECURITY"] = ch
            all_degradations.extend(deg)
            all_improvements.extend(imp)

        # 7. Performance
        b_perf = baseline.dimensions.get("PERFORMANCE")
        a_perf = after.dimensions.get("PERFORMANCE")
        if b_perf and a_perf:
            ch, deg, imp = self.perf_eval.compare_performance(b_perf, a_perf)
            dimension_changes["PERFORMANCE"] = ch
            all_degradations.extend(deg)
            all_improvements.extend(imp)

        # 8. Reliability
        b_rel = baseline.dimensions.get("RELIABILITY")
        a_rel = after.dimensions.get("RELIABILITY")
        if b_rel and a_rel:
            ch, deg, imp = self.rel_eval.compare_reliability(b_rel, a_rel)
            dimension_changes["RELIABILITY"] = ch
            all_degradations.extend(deg)
            all_improvements.extend(imp)

        # 9. Maintainability
        b_maint = baseline.dimensions.get("MAINTAINABILITY")
        a_maint = after.dimensions.get("MAINTAINABILITY")
        if b_maint and a_maint:
            ch, deg, imp = self.maint_eval.compare_maintainability(b_maint, a_maint)
            dimension_changes["MAINTAINABILITY"] = ch
            all_degradations.extend(deg)
            all_improvements.extend(imp)

        # Compute uncertainty delta
        b_unc = [d.uncertainty for d in baseline.dimensions.values()]
        a_unc = [d.uncertainty for d in after.dimensions.values()]
        mean_b_unc = sum(b_unc) / max(len(b_unc), 1)
        mean_a_unc = sum(a_unc) / max(len(a_unc), 1)
        unc_delta = mean_a_unc - mean_b_unc

        # Filter degradations that are within measurement uncertainty
        filtered_degradations = []
        for d in all_degradations:
            from_val = d.get("from")
            to_val = d.get("to")
            if isinstance(from_val, (int, float)) and isinstance(to_val, (int, float)):
                diff = abs(to_val - from_val)
                # If difference is smaller than mean uncertainty band, classify as UNCERTAIN
                if diff < mean_a_unc * 0.5 and not d.get("severity") == "CRITICAL":
                    continue  # Ignore within-uncertainty noise
            filtered_degradations.append(d)

        return QualityDelta(
            baseline_snapshot_id=baseline.snapshot_id,
            after_snapshot_id=after.snapshot_id,
            mission_id=after.mission_id,
            dimension_changes=dimension_changes,
            evidence_efficiency=eff,
            more_tests=more_tests,
            more_useful_evidence=more_useful_evidence,
            degradations=filtered_degradations,
            improvements=all_improvements,
            uncertainty_delta=unc_delta,
            timestamp=time.time(),
        )

    def classify_regression(self, degradation: Dict[str, Any]) -> QualityRegressionLevel:
        sev = degradation.get("severity", "").upper()
        if sev == "CRITICAL" or degradation.get("metric") in ("secret_exposure_attempts", "sandbox_violations", "boundary_violations"):
            return QualityRegressionLevel.CRITICAL
        if degradation.get("metric") in ("scc_size", "breaking_changes", "counterexamples", "mission_stalls"):
            return QualityRegressionLevel.SIGNIFICANT
        if degradation.get("metric") in ("complexity", "duplication", "p95_latency_ms", "flaky_rate"):
            return QualityRegressionLevel.MINOR
        return QualityRegressionLevel.UNCERTAIN
