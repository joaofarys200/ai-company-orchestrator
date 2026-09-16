"""
JARVIS OS — Phase 56: Convergence Experience Store
Stores and queries historical convergence patterns; memory is advisory, never sovereign authority.
"""

from __future__ import annotations

import time
from typing import Dict, Any, List, Optional


class ConvergenceExperienceStore:
    """Provides advisory guidance from past repair missions without replacing formal verification."""

    def __init__(self):
        self.known_patterns: List[Dict[str, Any]] = []

    def record_mission_outcome(
        self,
        mission_id: str,
        failure_signature: str,
        repair_sequence: List[str],
        converged: bool,
        cycles_encountered: int = 0,
        notes: str = "",
    ) -> None:
        """Records experience metadata for future advisory lookups."""
        self.known_patterns.append({
            "mission_id": mission_id,
            "failure_signature": failure_signature,
            "repair_sequence": list(repair_sequence),
            "converged": converged,
            "cycles_encountered": cycles_encountered,
            "notes": notes,
            "timestamp": time.time(),
        })

    def query_similar_patterns(self, failure_signature: str) -> List[Dict[str, Any]]:
        """Queries historical outcomes matching or containing the given failure signature."""
        return [
            p for p in self.known_patterns
            if failure_signature.lower() in p["failure_signature"].lower()
        ]

    def get_advisory_heuristic(self, failure_signature: str) -> Dict[str, Any]:
        """Provides ordering guidance while emphasizing epistemic limitation."""
        matches = self.query_similar_patterns(failure_signature)
        if not matches:
            return {
                "has_guidance": False,
                "confidence": 0.0,
                "advisory_notes": "No historical precedent found.",
                "authority": "FORMAL_ANALYSIS_REQUIRED",
            }

        successful = [m for m in matches if m["converged"]]
        success_rate = len(successful) / len(matches)
        return {
            "has_guidance": True,
            "historical_matches": len(matches),
            "historical_success_rate": round(success_rate, 2),
            "advisory_notes": f"Observed {len(matches)} past occurrences; memory suggests cautious sequencing.",
            "authority": "ADVISORY_ONLY_NOT_FORMAL_PROOF",
        }
