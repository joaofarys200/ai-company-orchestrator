"""
JARVIS OS — Phase 56: Oscillation Detector
Detects cycle patterns, alternating failure signatures, and ping-pong state oscillations.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple
from agents.repair_convergence_governance.models import (
    OscillationReport,
    RepairStepSnapshot,
)


class OscillationDetector:
    """Detects cycles, ping-pong state bouncing, and alternating error patterns in repair attempts."""

    def __init__(self, max_cycle_length: int = 4):
        self.max_cycle_length = max_cycle_length

    def detect_oscillation(self, history: List[RepairStepSnapshot]) -> OscillationReport:
        """Analyzes snapshot history for periodic repeating patterns."""
        if len(history) < 3:
            return OscillationReport(
                oscillating=False,
                cycle_length=0,
                cycle_states=[],
                repeating_signatures=[],
                explanation="Insufficient history to detect oscillation."
            )

        # Extract signatures
        state_hashes = [s.state_hash for s in history]
        failure_signatures = [tuple(sorted(s.active_failures)) for s in history]

        n = len(history)

        # 1. Direct Ping-Pong Failure Alternation (A -> B -> A for n >= 3)
        if n >= 3 and failure_signatures[-1] == failure_signatures[-3] and failure_signatures[-1] != failure_signatures[-2]:
            cycle_states = [history[-3].iteration_id, history[-2].iteration_id, history[-1].iteration_id]
            return OscillationReport(
                oscillating=True,
                cycle_length=2,
                cycle_states=cycle_states,
                repeating_signatures=[str(failure_signatures[-1]), str(failure_signatures[-2])],
                explanation=f"Ping-pong failure alternation (period 2) detected: {failure_signatures[-1]} ↔ {failure_signatures[-2]} across steps {cycle_states}."
            )

        # 2. Exact State Hash Cycle Detection
        for k in range(2, min(self.max_cycle_length + 1, n // 2 + 1)):
            pattern1 = state_hashes[-k:]
            pattern2 = state_hashes[-2 * k : -k]
            if pattern1 == pattern2:
                cycle_states = [s.iteration_id for s in history[-2 * k :]]
                return OscillationReport(
                    oscillating=True,
                    cycle_length=k,
                    cycle_states=cycle_states,
                    repeating_signatures=[str(sig) for sig in failure_signatures[-k:]],
                    explanation=f"Exact state hash cycle of length {k} detected across iterations {cycle_states}."
                )

        # 3. Failure Signature Oscillation (Ping-Pong across longer sequences)
        for k in range(2, min(self.max_cycle_length + 1, n // 2 + 1)):
            sig1 = failure_signatures[-k:]
            sig2 = failure_signatures[-2 * k : -k]
            if sig1 == sig2 and len(set(sig1)) > 1:
                cycle_states = [s.iteration_id for s in history[-2 * k :]]
                return OscillationReport(
                    oscillating=True,
                    cycle_length=k,
                    cycle_states=cycle_states,
                    repeating_signatures=[str(sig) for sig in sig1],
                    explanation=f"Failure signature ping-pong oscillation of period {k} detected across iterations {cycle_states}."
                )

        return OscillationReport(
            oscillating=False,
            cycle_length=0,
            cycle_states=[],
            repeating_signatures=[],
            explanation="No oscillating patterns or cycles detected."
        )
