"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Repair Scheduler.
Schedules ordered repairs into waves of independent operations for safe execution.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple


class RepairScheduler:
    """
    Groups topologically sorted repairs into executable waves.
    Repairs in the same wave have no mutual dependencies.
    """

    def schedule_waves(
        self,
        ordered_repair_ids: List[str],
        dependencies: List[Tuple[str, str]],  # (producer, consumer)
    ) -> List[List[str]]:
        if not ordered_repair_ids:
            return []

        adj: Dict[str, Set[str]] = {r: set() for r in ordered_repair_ids}
        in_deps: Dict[str, Set[str]] = {r: set() for r in ordered_repair_ids}

        for prod, cons in dependencies:
            if prod in adj and cons in in_deps:
                adj[prod].add(cons)
                in_deps[cons].add(prod)

        remaining = set(ordered_repair_ids)
        waves: List[List[str]] = []

        while remaining:
            # Candidates with zero unresolved dependencies among remaining items
            current_wave = [r for r in remaining if not (in_deps[r] & remaining)]
            if not current_wave:
                # Cycle fallback: take first item deterministically
                current_wave = [sorted(list(remaining))[0]]

            current_wave.sort()
            waves.append(current_wave)
            for r in current_wave:
                remaining.remove(r)

        return waves
