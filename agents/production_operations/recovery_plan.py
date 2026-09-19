"""
Phase 71 — Recovery Planning Engine
Constructs formal recovery plans evaluating preconditions, risks, rollback actions, and governance safety.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional
from .models import (
    Incident,
    IncidentCategory,
    RecoveryPlan,
    RecoveryStrategy,
    RemediationSafety,
    RootCauseHypothesis,
    SeverityLevel,
)


class RecoveryPlanner:
    """
    Synthesizes actionable recovery plans for diagnosed incidents.
    """

    def __init__(self, service_id: str):
        self.service_id = service_id
        self._plans: List[RecoveryPlan] = []

    def plan_recovery(
        self,
        incident: Incident,
        hypothesis: Optional[RootCauseHypothesis] = None,
        allow_destructive: bool = False,
    ) -> RecoveryPlan:
        """
        Synthesizes a RecoveryPlan based on incident category, severity, and root cause hypothesis.
        """
        # Strategy selection
        if incident.severity == SeverityLevel.SEV0:
            strategy = RecoveryStrategy.ROLLBACK_RELEASE
            safety = RemediationSafety.ALLOWED  # Rollback is authorized for SEV0
            preconditions = ["Checkpoint verified", "Target release validated"]
            expected_effect = "Revert to previous stable release baseline to halt corruption or total outage."
            risk_level = "MEDIUM"
            required_evidence = ["SEV0 incident confirmed", "Rollback checkpoint available"]
            rollback_action = "Re-apply current state if rollback fails"
            verification_plan = ["healthcheck_all", "verify_release_hash"]

        elif incident.category in {IncidentCategory.PROCESS_CRASH, IncidentCategory.WEBSOCKET_FAILURE}:
            strategy = RecoveryStrategy.RESTART_PROCESS
            safety = RemediationSafety.ALLOWED
            preconditions = ["Process PID identified or down", "Local runtime controller active"]
            expected_effect = "Relaunch dead process cleanly."
            risk_level = "LOW"
            required_evidence = ["Process down or unresponsive"]
            rollback_action = "Terminate process if restart enters crash loop"
            verification_plan = ["check_process_alive", "check_http_reachable"]

        elif incident.category == IncidentCategory.DATABASE_FAILURE:
            strategy = RecoveryStrategy.RECONNECT_DEPENDENCY
            safety = RemediationSafety.ALLOWED
            preconditions = ["Database host reachable", "Credentials valid"]
            expected_effect = "Reset database connection pool and re-establish session."
            risk_level = "LOW"
            required_evidence = ["Connection error evidence"]
            rollback_action = "Isolate database client"
            verification_plan = ["check_database_connectivity"]

        elif incident.category == IncidentCategory.RESOURCE_EXHAUSTION:
            strategy = RecoveryStrategy.CLEAR_TRANSIENT_STATE
            safety = RemediationSafety.ALLOWED
            preconditions = ["Transient cache exists", "Persistent storage unaffected"]
            expected_effect = "Flush in-memory LRU caches to alleviate OOM pressure."
            risk_level = "LOW"
            required_evidence = ["Memory pressure > 85%"]
            rollback_action = "None (cache is ephemeral)"
            verification_plan = ["check_memory_usage"]

        elif incident.category == IncidentCategory.CONFIGURATION_FAILURE:
            strategy = RecoveryStrategy.RELOAD_CONFIGURATION
            safety = RemediationSafety.ALLOWED
            preconditions = ["Valid backup config on disk", "Schema matches"]
            expected_effect = "Reload verified configuration from disk."
            risk_level = "LOW"
            required_evidence = ["Config drift observed"]
            rollback_action = "Revert to previous config snapshot"
            verification_plan = ["check_response_schema"]

        elif incident.category == IncidentCategory.RESTART_LOOP:
            # If crashing repeatedly, restart is futile -> rollback or escalate
            strategy = RecoveryStrategy.ROLLBACK_RELEASE
            safety = RemediationSafety.ALLOWED
            preconditions = ["Valid previous release available"]
            expected_effect = "Rollback to previous release to break restart loop."
            risk_level = "MEDIUM"
            required_evidence = ["Restart loop >= 3"]
            rollback_action = "Escalate to human operator"
            verification_plan = ["check_process_alive", "check_restart_rate"]

        else:
            strategy = RecoveryStrategy.ESCALATE_HUMAN
            safety = RemediationSafety.ALLOWED
            preconditions = ["Human review queue available"]
            expected_effect = "Transfer incident to engineer for manual triage."
            risk_level = "MINIMAL"
            required_evidence = ["Uncertain root cause or unmapped category"]
            rollback_action = None
            verification_plan = ["confirm_ticket_created"]

        # Check safety policy
        if not allow_destructive and strategy in {RecoveryStrategy.RESTORE_CHECKPOINT} and incident.severity != SeverityLevel.SEV0:
            safety = RemediationSafety.HIGH_RISK_WITHOUT_APPROVAL

        plan = RecoveryPlan(
            plan_id=f"rec-plan-{uuid.uuid4().hex[:8]}",
            incident_id=incident.incident_id,
            strategy=strategy,
            safety=safety,
            preconditions=preconditions,
            expected_effect=expected_effect,
            risk_level=risk_level,
            required_evidence=required_evidence,
            rollback_action=rollback_action,
            verification_plan=verification_plan,
            authorized_by_policy=(safety == RemediationSafety.ALLOWED),
            created_at=time.time(),
        )
        self._plans.append(plan)
        return plan

    def get_plans(self) -> List[RecoveryPlan]:
        return list(self._plans)
