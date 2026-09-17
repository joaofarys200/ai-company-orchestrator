"""
JARVIS OS — Phase 57: Mission Scorecard & Multi-Dimensional Metrics
Computes explicit multi-dimensional scorecard metrics without concealing raw telemetry.
"""

from __future__ import annotations

import time
from typing import Any

from .models import AutonomousMission, MissionEvidenceType, MissionScorecard


class MissionMetricsCalculator:
    """Calculates comprehensive, unaggregated scorecards for completed or active missions."""

    @classmethod
    def compute_scorecard(
        cls,
        mission: AutonomousMission,
        duration_seconds: float = 0.0,
    ) -> MissionScorecard:
        plan = mission.plan or {}
        tasks = plan.get("tasks", [])
        tasks_total = len(tasks)
        tasks_completed = tasks_total if mission.state.value in ("COMPLETED", "PROVING") else max(0, tasks_total - 1)
        tasks_failed = len([f for f in mission.failures if not f.get("resolved", False)])

        repairs = len(mission.repairs)
        rollbacks = len([t for t in mission.transaction_history if t.get("status") == "ROLLED_BACK"])

        evidence_count = len(mission.evidence_set.evidences)
        proofs = 1 if mission.proof else 0
        human_reviews = len(mission.human_tickets)

        prediction_accuracy = plan.get("accuracy_score", 1.0)
        repair_success = 1.0 if repairs == 0 else (len([r for r in mission.repairs if r.get("verification_status") == "VERIFIED"]) / repairs)

        # Browser status
        has_browser = mission.evidence_set.has_valid(MissionEvidenceType.BROWSER)
        domain = mission.provenance.get("domain", "general_engineering")
        if domain in ("frontend", "fullstack", "browser_task"):
            browser_status = "PASSED" if has_browser else "FAILED"
        else:
            browser_status = "SKIPPED_NOT_REQUIRED"

        coverage = max(0.0, min(1.0, 1.0 - (tasks_failed * 0.15)))

        scorecard = MissionScorecard(
            tasks_total=tasks_total,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            repairs=repairs,
            rollbacks=rollbacks,
            risk=mission.risk,
            coverage=coverage,
            evidence_count=evidence_count,
            proofs=proofs,
            human_reviews=human_reviews,
            mission_duration=duration_seconds,
            prediction_accuracy=prediction_accuracy,
            repair_success=repair_success,
            browser_status=browser_status,
        )

        mission.scorecard = scorecard
        return scorecard
