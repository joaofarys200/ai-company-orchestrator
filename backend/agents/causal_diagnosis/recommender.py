"""
JARVIS OS — Phase 78: Autonomous Causal Diagnosis & Root-Cause Analysis
Module: recommender.py
Formulates targeted corrective actions linked directly to confirmed root-cause nodes.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from .models import CausalHypothesis, CorrectiveAction


class CorrectiveActionRecommender:
    """
    Formulates evidence-grounded corrective remediation recommendations
    addressing the upstream root causes rather than treating downstream symptoms.
    """

    @staticmethod
    def recommend_actions_for_hypothesis(
        hypothesis: CausalHypothesis,
        subsystem: str,
        root_cause_description: str,
    ) -> List[CorrectiveAction]:
        """Generate targeted remediation recommendations."""
        actions: List[CorrectiveAction] = []

        act_id = f"act_{uuid.uuid4().hex[:8]}"
        action = CorrectiveAction(
            action_id=act_id,
            target_root_cause_id=hypothesis.root_cause_node_id,
            action_type="UPSTREAM_REMEDIATION",
            description=f"Remediate {subsystem} defect: '{root_cause_description}'.",
            risks="Low risk if verified via transactional sandbox before deployment.",
            expected_effect=f"Eliminate causal trigger and restore healthy telemetry in {subsystem}.",
            verification_criteria="Post-remediation test suite execution with 0 failures and latency SLO restored.",
        )
        actions.append(action)
        return actions
