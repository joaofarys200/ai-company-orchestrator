"""
Phase 71 — Deterministic Severity Classifier
Classifies incident severity into SEV0..SEV4 strictly based on explicit deterministic rules.
"""

from __future__ import annotations

from typing import List, Tuple
from .models import IncidentCategory, SeverityLevel


class SeverityClassifier:
    """
    Deterministic rule-based severity classifier.
    Never assigns arbitrary severities; records the triggered rule and rationale.
    """

    @classmethod
    def classify(
        self,
        category: IncidentCategory,
        evidence: List[str],
        impact_metrics: dict[str, float] | None = None,
    ) -> Tuple[SeverityLevel, str, str]:
        """
        Returns (SeverityLevel, rule_name, rationale).
        """
        metrics = impact_metrics or {}
        error_rate = metrics.get("error_rate", 0.0)
        availability = metrics.get("availability", 1.0)
        restart_count = metrics.get("restart_count", 0)

        # Rule 1: SEV0 - Complete outage, database failure with corruption, or uncontrollable crash loop
        if category == IncidentCategory.DATABASE_FAILURE and any("corrupt" in e.lower() or "data loss" in e.lower() for e in evidence):
            return (
                SeverityLevel.SEV0,
                "RULE_DB_CORRUPTION_SEV0",
                "Database failure with corruption risk requires immediate operational halt and mandatory rollback."
            )

        if category == IncidentCategory.RESTART_LOOP and restart_count >= 5:
            return (
                SeverityLevel.SEV0,
                "RULE_CRASH_LOOP_FATAL_SEV0",
                f"Continuous crash loop detected (restarts={restart_count}) with total service failure."
            )

        if availability <= 0.0:
            return (
                SeverityLevel.SEV0,
                "RULE_ZERO_AVAILABILITY_SEV0",
                "Complete total loss of service availability (availability=0.0)."
            )

        # Rule 2: SEV1 - High impact unavailability or severe service failure
        if category in {IncidentCategory.PROCESS_CRASH, IncidentCategory.DATABASE_FAILURE}:
            return (
                SeverityLevel.SEV1,
                "RULE_CRITICAL_SERVICE_DOWN_SEV1",
                f"Critical component failure: {category.value} causing severe unavailability."
            )

        if category == IncidentCategory.HTTP_5XX and error_rate >= 0.5:
            return (
                SeverityLevel.SEV1,
                "RULE_MASSIVE_5XX_OUTAGE_SEV1",
                f"Massive 5XX error rate ({error_rate * 100:.1f}%) impacting majority of traffic."
            )

        if category == IncidentCategory.RESOURCE_EXHAUSTION and any("oom" in e.lower() or "out of memory" in e.lower() for e in evidence):
            return (
                SeverityLevel.SEV1,
                "RULE_RESOURCE_EXHAUSTION_SEV1",
                "Out of memory or CPU starvation causing service unresponsiveness."
            )

        # Rule 3: SEV2 - Significant degradation
        if category in {IncidentCategory.ERROR_RATE_SLO_BREACH, IncidentCategory.DEPENDENCY_FAILURE}:
            return (
                SeverityLevel.SEV2,
                "RULE_DEGRADATION_SEV2",
                f"Significant service degradation: {category.value} with error rate {error_rate * 100:.1f}%."
            )

        if category == IncidentCategory.HTTP_TIMEOUT:
            return (
                SeverityLevel.SEV2,
                "RULE_HTTP_TIMEOUT_SEV2",
                "Elevated upstream or gateway timeouts causing functional degradation."
            )

        if category == IncidentCategory.WEBSOCKET_FAILURE:
            return (
                SeverityLevel.SEV2,
                "RULE_WEBSOCKET_DOWN_SEV2",
                "Realtime communication channel failure affecting interactive capabilities."
            )

        # Rule 4: SEV3 - Limited error / partial impact
        if category in {IncidentCategory.LATENCY_SLO_BREACH, IncidentCategory.HEALTHCHECK_FAILURE}:
            return (
                SeverityLevel.SEV3,
                "RULE_PARTIAL_IMPACT_SEV3",
                f"Partial performance or health impact: {category.value}."
            )

        if category == IncidentCategory.CONFIGURATION_FAILURE:
            return (
                SeverityLevel.SEV3,
                "RULE_CONFIG_WARNING_SEV3",
                "Configuration inconsistency or drift without immediate hard crash."
            )

        # Rule 5: SEV4 - Low-priority anomaly without confirmed functional failure
        return (
            SeverityLevel.SEV4,
            "RULE_LOW_ANOMALY_SEV4",
            f"Observed anomaly {category.value} without confirmed end-user impairment."
        )
