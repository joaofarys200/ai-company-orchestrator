"""
JARVIS OS — Phase 56: Cycle Detector
Detects exact state recurrence, ping-pong failure oscillations, subset cycles, repeated repairs, and multi-order loops.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple
from agents.repair_convergence_governance.models import (
    CycleReport,
    CycleType,
    RepairStepSnapshot,
    compute_deterministic_hash,
)


class CycleDetector:
    """Deterministic cycle detection across repair state histories."""

    def __init__(self, history_window: int = 25, max_cycle_order: int = 5):
        self.history_window = history_window
        self.max_cycle_order = max_cycle_order

    def detect_cycles(self, history: List[RepairStepSnapshot]) -> CycleReport:
        """Analyzes snapshot history to identify repetitive cycles."""
        if len(history) < 2:
            return CycleReport(cycle_detected=False, explanation="Insufficient history to detect cycles.")

        window = history[-self.history_window:]

        # 1. Exact State Hash Cycle
        exact_cycle = self._detect_exact_state_cycle(window)
        if exact_cycle.cycle_detected:
            return exact_cycle

        # 2. Ping-Pong Failure Cycle (A -> B -> A)
        ping_pong = self._detect_ping_pong_failures(window)
        if ping_pong.cycle_detected:
            return ping_pong

        # 3. 3-Step Failure Cycle (A -> B -> C -> A)
        three_cycle = self._detect_3_step_cycle(window)
        if three_cycle.cycle_detected:
            return three_cycle

        # 4. Multi-Order Failure/State Cycle (Order 4..N)
        order_n = self._detect_order_n_cycle(window)
        if order_n.cycle_detected:
            return order_n

        # 5. Repeated Repair Attempt without Progress
        repeated_repair = self._detect_repeated_repair(window)
        if repeated_repair.cycle_detected:
            return repeated_repair

        # 6. Subset Oscillation Cycle
        subset_cycle = self._detect_subset_oscillation(window)
        if subset_cycle.cycle_detected:
            return subset_cycle

        return CycleReport(cycle_detected=False, explanation="No cyclic patterns detected in repair history.")

    def _detect_exact_state_cycle(self, window: List[RepairStepSnapshot]) -> CycleReport:
        hashes = [s.state_hash for s in window]
        seen_indices: Dict[str, int] = {}

        for idx, h in enumerate(hashes):
            if h in seen_indices:
                period = idx - seen_indices[h]
                if period > 0:
                    repeating = hashes[seen_indices[h]:idx + 1]
                    return CycleReport(
                        cycle_detected=True,
                        cycle_type=CycleType.EXACT_STATE_CYCLE,
                        cycle_period=period,
                        repeating_states=repeating,
                        explanation=f"Exact state hash repeated after {period} iterations (hash: {h})."
                    )
            seen_indices[h] = idx

        return CycleReport(cycle_detected=False)

    def _detect_ping_pong_failures(self, window: List[RepairStepSnapshot]) -> CycleReport:
        if len(window) < 3:
            return CycleReport(cycle_detected=False)

        # Check the last 6 steps
        recent = window[-6:]
        failure_sets = [frozenset(s.active_failures) for s in recent]

        for i in range(len(failure_sets) - 2):
            if failure_sets[i] == failure_sets[i + 2] and failure_sets[i] != failure_sets[i + 1]:
                f_a = sorted(list(failure_sets[i]))
                f_b = sorted(list(failure_sets[i + 1]))
                return CycleReport(
                    cycle_detected=True,
                    cycle_type=CycleType.PING_PONG_FAILURE_CYCLE,
                    cycle_period=2,
                    repeating_failures=f_a,
                    explanation=f"Ping-pong failure alternation (period 2) detected between set {f_a} and {f_b}."
                )

        return CycleReport(cycle_detected=False)

    def _detect_3_step_cycle(self, window: List[RepairStepSnapshot]) -> CycleReport:
        """Detects A -> B -> C -> A pattern in failures or state fingerprints."""
        if len(window) < 4:
            return CycleReport(cycle_detected=False)

        recent = window[-8:]
        failure_sets = [frozenset(s.active_failures) for s in recent]

        for i in range(len(failure_sets) - 3):
            f_a = failure_sets[i]
            f_b = failure_sets[i + 1]
            f_c = failure_sets[i + 2]
            f_next = failure_sets[i + 3]
            if f_a == f_next and f_a != f_b and f_b != f_c and f_a != f_c:
                return CycleReport(
                    cycle_detected=True,
                    cycle_type=CycleType.EXACT_STATE_CYCLE,
                    cycle_period=3,
                    repeating_failures=sorted(list(f_a)),
                    explanation=f"3-phase cycle detected: A -> B -> C -> A across steps {recent[i].iteration_id} to {recent[i+3].iteration_id}."
                )

        return CycleReport(cycle_detected=False)

    def _detect_order_n_cycle(self, window: List[RepairStepSnapshot]) -> CycleReport:
        """Detects generalized order N periodic cycles up to max_cycle_order."""
        if len(window) < 4:
            return CycleReport(cycle_detected=False)

        sigs = [tuple(sorted(s.active_failures)) for s in window]
        n = len(sigs)

        for period in range(2, min(self.max_cycle_order + 1, n // 2 + 1)):
            pat1 = sigs[-period:]
            pat2 = sigs[-2 * period : -period]
            if pat1 == pat2 and len(set(pat1)) > 1:
                return CycleReport(
                    cycle_detected=True,
                    cycle_type=CycleType.EXACT_STATE_CYCLE,
                    cycle_period=period,
                    repeating_failures=[str(f) for f in pat1],
                    explanation=f"Periodic cycle of length {period} detected across repeating failure signatures."
                )

        return CycleReport(cycle_detected=False)

    def _detect_repeated_repair(self, window: List[RepairStepSnapshot]) -> CycleReport:
        """Detects applying the same patch/repair repeatedly without changing failure set."""
        if len(window) < 2:
            return CycleReport(cycle_detected=False)

        last_step = window[-1]
        prev_step = window[-2]

        # Check if same patches applied and active failures identical
        if (
            last_step.patches_applied
            and last_step.patches_applied == prev_step.patches_applied
            and sorted(last_step.active_failures) == sorted(prev_step.active_failures)
        ):
            return CycleReport(
                cycle_detected=True,
                cycle_type=CycleType.REPEATED_REPAIR_CYCLE,
                cycle_period=1,
                repeating_failures=sorted(last_step.active_failures),
                explanation=f"Identical repair patch {last_step.patches_applied} reapplied without altering active failures."
            )

        return CycleReport(cycle_detected=False)

    def _detect_subset_oscillation(self, window: List[RepairStepSnapshot]) -> CycleReport:
        if len(window) < 4:
            return CycleReport(cycle_detected=False)

        recent = window[-8:]
        failure_sets = [set(s.active_failures) for s in recent]

        for i in range(len(failure_sets) - 3):
            s1 = failure_sets[i]
            s2 = failure_sets[i + 1]
            s3 = failure_sets[i + 2]
            s4 = failure_sets[i + 3]

            if (s1.issubset(s2) or s2.issubset(s1)) and s1 == s3 and s2 == s4 and s1 != s2:
                return CycleReport(
                    cycle_detected=True,
                    cycle_type=CycleType.SUBSET_OSCILLATION_CYCLE,
                    cycle_period=2,
                    repeating_failures=sorted(list(s1)),
                    explanation="Subset oscillation cycle: failure sets alternating between sub/supersets."
                )

        return CycleReport(cycle_detected=False)
