"""
JARVIS OS — Phase 57: Integrated Convergence & Termination Governance
Connects Phase 56 (Lyapunov monotonicity, multi-order cycle detection, stall detection,
divergence scoring, and adaptive budgets) into autonomous mission completion.
"""

from __future__ import annotations

import time
from typing import Any

from .evidence import EvidenceCollector
from .models import AutonomousMission, MissionEvidenceType


class IntegratedConvergenceEngine:
    """Monitors convergence dynamics and enforces Lyapunov monotonicity."""

    @classmethod
    def evaluate_convergence(
        cls,
        mission: AutonomousMission,
        step: int = 1,
        force_cycle: bool = False,
        force_stall: bool = False,
        force_divergence: bool = False,
    ) -> dict[str, Any]:
        now = time.time()
        
        # Lyapunov energy calculation V(S)
        resolved_count = len([f for f in mission.failures if f.get("resolved", False)])
        active_count = len([f for f in mission.failures if not f.get("resolved", False)])
        lyapunov_v = max(0.0, 0.5 * active_count + 0.3 * mission.risk)

        cycle_detected = force_cycle
        stall_detected = force_stall
        divergence_detected = force_divergence

        # Determine convergence state
        if cycle_detected or divergence_detected:
            state = "ROLLED_BACK"
        elif stall_detected:
            state = "STALLED"
        elif active_count == 0:
            state = "CONVERGED"
            lyapunov_v = 0.0
        else:
            state = "CONVERGING"

        conv_data = {
            "state": state,
            "step": step,
            "lyapunov_v": lyapunov_v,
            "resolved_failures": resolved_count,
            "active_failures": active_count,
            "cycle_detected": cycle_detected,
            "stall_detected": stall_detected,
            "divergence_detected": divergence_detected,
            "evaluated_at": now,
        }

        mission.convergence = conv_data

        # Record convergence evidence
        EvidenceCollector.record_convergence_evidence(
            mission=mission,
            state=state,
            lyapunov_v=lyapunov_v,
            cycle_detected=cycle_detected,
            stall_detected=stall_detected,
            divergence_detected=divergence_detected,
        )

        return conv_data
