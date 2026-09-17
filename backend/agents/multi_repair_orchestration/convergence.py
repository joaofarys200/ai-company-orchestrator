"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Repair Convergence Engine.
Evaluates systemic convergence across multiple repairs, detecting divergence, stalls,
and distinguishing revealed failures from regressions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from agents.multi_repair_orchestration.models import (
    ConvergenceState,
    FailureItem,
    RepairTransaction,
    RevealedFailureType,
)


class RepairConvergenceEngine:
    """
    Monitors progress towards full system stability.
    Ensures that repairs resolve target failures without introducing regressions or diverging.
    """

    def evaluate_convergence(
        self,
        transaction: RepairTransaction,
        target_failures: List[FailureItem],
        active_failures: List[FailureItem],
        iteration_count: int = 1,
        max_iterations: int = 5,
        invariants_satisfied: bool = True,
    ) -> Tuple[ConvergenceState, Dict[str, Any]]:
        target_ids: Set[str] = {f.failure_id for f in target_failures}
        active_ids: Set[str] = {f.failure_id for f in active_failures}

        # Resolved target failures
        resolved_count = len(target_ids - active_ids)
        new_failures = [f for f in active_failures if f.failure_id not in target_ids]

        # Categorize new failures
        revealed_count = 0
        regression_count = 0
        for nf in new_failures:
            if nf.failure_type == RevealedFailureType.REVEALED_FAILURE:
                revealed_count += 1
            elif nf.failure_type == RevealedFailureType.REGRESSION_FAILURE:
                regression_count += 1

        details = {
            "resolved_count": resolved_count,
            "target_count": len(target_failures),
            "new_failures_count": len(new_failures),
            "revealed_count": revealed_count,
            "regression_count": regression_count,
            "iteration": iteration_count,
        }

        # 1. Blocked condition
        if not invariants_satisfied:
            return ConvergenceState.BLOCKED, details

        # 2. Divergence condition: new regressions or runaway failure count
        if regression_count > 0 or len(active_failures) > len(target_failures) * 2:
            return ConvergenceState.DIVERGING, details

        # 3. Convergence condition: all target resolved, zero blocking new failures, invariants pass
        if len(active_ids) == 0 and invariants_satisfied:
            return ConvergenceState.CONVERGED, details

        # 4. Stalled condition: iteration limit reached without resolution
        if iteration_count >= max_iterations and resolved_count == 0:
            return ConvergenceState.STALLED, details

        # 5. Converging condition: making positive progress
        if resolved_count > 0:
            return ConvergenceState.CONVERGING, details

        return ConvergenceState.UNKNOWN, details

    def classify_failure(
        self,
        failure: FailureItem,
        pre_existing_untested_areas: List[str] | None = None,
        caused_by_patch: bool = False,
    ) -> RevealedFailureType:
        """
        Differentiates revealed failures from regression failures:
        - If a patch fixed a blocker and exposed an existing unexercised branch -> REVEALED_FAILURE
        - If a patch altered a previously working route/contract -> REGRESSION_FAILURE
        """
        pre_existing_untested_areas = pre_existing_untested_areas or []

        if caused_by_patch:
            return RevealedFailureType.REGRESSION_FAILURE

        if failure.file_path in pre_existing_untested_areas or failure.symbol in pre_existing_untested_areas:
            return RevealedFailureType.REVEALED_FAILURE

        return RevealedFailureType.NEW_UNRELATED_FAILURE
