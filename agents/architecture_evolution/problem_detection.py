"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: problem_detection.py
Synthesizes and formalizes observed architectural smells into structured
ArchitectureProblem instances, filtering false positives and attaching provenance.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional

from .models import (
    ArchitectureProblem,
    ArchitectureSnapshot,
    ObservationStatus,
    ProblemCategory,
    ProblemSeverity,
)
from .observation import ArchitectureObserver


class ArchitectureProblemDetector:
    """Detects and formalizes architecture problems from observations."""

    def __init__(self, observer: Optional[ArchitectureObserver] = None):
        self.observer = observer or ArchitectureObserver()

    def detect_problems(self, snapshot: ArchitectureSnapshot) -> List[ArchitectureProblem]:
        """Runs observation and formalizes genuine architectural problems."""
        raw_observations = self.observer.observe(snapshot)
        problems: List[ArchitectureProblem] = []

        for obs in raw_observations:
            # False positive rejection filters
            if self._is_false_positive(obs, snapshot):
                continue

            target_node = obs.get("target_node", "unknown")
            cat = obs.get("category", ProblemCategory.COUPLING)
            sev = obs.get("severity", ProblemSeverity.MEDIUM)
            status = obs.get("status", ObservationStatus.OBSERVED)

            # Generate deterministic problem ID
            raw_id = f"{cat.value}:{target_node}:{obs.get('smell_type')}"
            problem_id = f"prob_{cat.value.lower()}_{hashlib.sha256(raw_id.encode()).hexdigest()[:8]}"

            # Determine affected symbols
            affected_symbols = [
                s for s in snapshot.symbols
                if any(node in s for node in obs.get("affected_nodes", []))
            ][:15]

            prob = ArchitectureProblem(
                problem_id=problem_id,
                category=cat,
                affected_nodes=obs.get("affected_nodes", [target_node]),
                affected_symbols=affected_symbols,
                evidence=obs.get("evidence", {}),
                severity=sev,
                confidence=obs.get("confidence", 0.9),
                constraints=[],
                provenance={
                    "snapshot_id": snapshot.snapshot_id,
                    "snapshot_hash": snapshot.snapshot_hash,
                    "detector": "ArchitectureProblemDetector",
                    "timestamp": time.time(),
                    "smell_type": obs.get("smell_type"),
                },
                status=status,
            )
            problems.append(prob)

        return problems

    def _is_false_positive(self, obs: Dict[str, Any], snapshot: ArchitectureSnapshot) -> bool:
        """Reject common architectural false smells (e.g. test harnesses, barrels)."""
        target = str(obs.get("target_node", "")).lower()

        # 1. Test utilities and test runners are naturally high fan-in/fan-out
        if any(term in target for term in ["test", "fixture", "conftest", "mock", "stub"]):
            if obs.get("category") == ProblemCategory.COUPLING:
                return True

        # 2. Canonical index / __init__ barrel files are meant to re-export
        if target.endswith("__init__.py") or target.endswith("index.ts") or target.endswith("index.js"):
            if obs.get("smell_type") in ["excessive_fan_out", "high_fan_in_hub"]:
                return True

        # 3. Deliberate microservice / IPC boundaries
        if "ipc" in target or "bridge" in target:
            if obs.get("smell_type") == "contract_concentration" and obs.get("evidence", {}).get("consumer_count", 0) < 8:
                return True

        return False
