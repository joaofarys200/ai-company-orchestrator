"""
Phase 72 — Preventive Action Planner
Synthesizes structured preventive plans from calibrated risk predictions.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .models import (
    GovernanceDecision,
    PreventiveAction,
    PreventiveActionStatus,
    PreventiveActionType,
    PreventivePlan,
    RiskLevel,
    RiskPrediction,
)


class PreventivePlanner:
    """Selects and sequences authorized preventive remediations."""

    def plan(
        self,
        prediction: RiskPrediction,
        authorized_actions: Optional[List[PreventiveActionType]] = None,
    ) -> PreventivePlan:
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        service = prediction.target
        actions: List[PreventiveAction] = []
        now = time.time()

        if authorized_actions is None:
            authorized_actions = list(PreventiveActionType)

        # 1. Low Risk or Normal condition
        if prediction.risk_level == RiskLevel.LOW:
            actions.append(
                PreventiveAction(
                    action_id=f"act_{uuid.uuid4().hex[:6]}",
                    action_type=PreventiveActionType.INCREASE_OBSERVATION_FREQUENCY,
                    target_service=service,
                    reason="Low predicted risk detected; increasing telemetry polling cadence.",
                    risk_level=RiskLevel.LOW,
                    expected_effect="Higher temporal resolution of telemetry without service impact.",
                    verification_plan="Verify telemetry sample count increases over next 60s.",
                    rollback_action="Reset observation frequency to default 10s interval.",
                    status=PreventiveActionStatus.PLANNED,
                )
            )

        # 2. Medium Risk (latency, memory, or dependency degradation)
        elif prediction.risk_level == RiskLevel.MEDIUM:
            if "LATENCY" in prediction.failure_class or "RESOURCE" in prediction.failure_class:
                actions.append(
                    PreventiveAction(
                        action_id=f"act_{uuid.uuid4().hex[:6]}",
                        action_type=PreventiveActionType.REBUILD_CACHE,
                        target_service=service,
                        reason="Telemetry indicates resource pressure and latency drift.",
                        risk_level=RiskLevel.LOW,
                        expected_effect="Evict stale cache entries to reduce memory overhead and latency.",
                        verification_plan="Check memory drop and p95 latency normalization.",
                        rollback_action="Restore previous cache snapshot if hit rate drops below 50%.",
                        status=PreventiveActionStatus.PLANNED,
                    )
                )
            else:
                actions.append(
                    PreventiveAction(
                        action_id=f"act_{uuid.uuid4().hex[:6]}",
                        action_type=PreventiveActionType.RUN_ADDITIONAL_HEALTHCHECKS,
                        target_service=service,
                        reason="Medium predicted risk; triggering deep diagnostic health checks.",
                        risk_level=RiskLevel.LOW,
                        expected_effect="Confirm deep endpoint status and schema integrity.",
                        verification_plan="Verify all standard and dependency healthchecks return HEALTHY.",
                        rollback_action="None required (read-only diagnostic check).",
                        status=PreventiveActionStatus.PLANNED,
                    )
                )

        # 3. High Risk (imminent crash, restart loop, or SLO breach)
        elif prediction.risk_level == RiskLevel.HIGH:
            # Create checkpoint first
            actions.append(
                PreventiveAction(
                    action_id=f"act_{uuid.uuid4().hex[:6]}",
                    action_type=PreventiveActionType.CREATE_CHECKPOINT,
                    target_service=service,
                    reason="High failure probability; persisting system state prior to remediation.",
                    risk_level=RiskLevel.LOW,
                    expected_effect="Cryptographically signed rollback checkpoint created.",
                    verification_plan="Confirm checkpoint file exists and SHA-256 matches.",
                    rollback_action="Delete invalid checkpoint.",
                    status=PreventiveActionStatus.PLANNED,
                )
            )

            if "RESTART" in prediction.failure_class or "CRASH" in prediction.failure_class:
                actions.append(
                    PreventiveAction(
                        action_id=f"act_{uuid.uuid4().hex[:6]}",
                        action_type=PreventiveActionType.ROLLBACK_BEFORE_FAILURE,
                        target_service=service,
                        reason="Restart loop predicted with high confidence; preemptive rollback required.",
                        risk_level=RiskLevel.HIGH,
                        expected_effect="Service rolled back to known-stable prior release.",
                        verification_plan="Verify process boots and passes all 8 health checks.",
                        rollback_action="Re-escalate to HUMAN_REVIEW if rollback target fails.",
                        status=PreventiveActionStatus.PLANNED,
                    )
                )
            else:
                actions.append(
                    PreventiveAction(
                        action_id=f"act_{uuid.uuid4().hex[:6]}",
                        action_type=PreventiveActionType.RESTART_SERVICE,
                        target_service=service,
                        reason="Sustained degradation; preemptive graceful restart before hard crash.",
                        risk_level=RiskLevel.MEDIUM,
                        expected_effect="Clear memory leak and transient lock contention.",
                        verification_plan="Observe 30s stability window with 0 errors.",
                        rollback_action="Restore checkpoint if restart fails.",
                        status=PreventiveActionStatus.PLANNED,
                    )
                )

        # 4. Unknown or Insufficient Evidence
        else:
            actions.append(
                PreventiveAction(
                    action_id=f"act_{uuid.uuid4().hex[:6]}",
                    action_type=PreventiveActionType.HUMAN_REVIEW,
                    target_service=service,
                    reason="Risk prediction has UNKNOWN confidence or insufficient evidence.",
                    risk_level=RiskLevel.LOW,
                    expected_effect="Route to human engineering queue for investigation.",
                    verification_plan="Acknowledge operator response ticket.",
                    rollback_action="None required.",
                    status=PreventiveActionStatus.PLANNED,
                )
            )

        # Filter against authorized actions policy
        filtered_actions = [a for a in actions if a.action_type in authorized_actions]

        return PreventivePlan(
            plan_id=plan_id,
            prediction_id=prediction.prediction_id,
            service=service,
            actions=filtered_actions,
            governance_decision=GovernanceDecision.PENDING_REVIEW,
            created_at=now,
        )
