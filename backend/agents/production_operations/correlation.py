"""
Phase 71 — Incident Correlation & Deduplication
Correlates symptoms to root incidents using dependency topology and causal evidence.
Guards against assuming causality solely by temporal proximity.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Set
from .models import Incident, IncidentCategory, IncidentCorrelation


class IncidentCorrelator:
    """
    Deduplicates and correlates cascading incidents across service dependency graphs.
    """

    # Upstream to downstream causal dependencies
    KNOWN_CAUSAL_CHAINS = {
        IncidentCategory.DATABASE_FAILURE: {
            IncidentCategory.HTTP_5XX,
            IncidentCategory.HTTP_TIMEOUT,
            IncidentCategory.ERROR_RATE_SLO_BREACH,
            IncidentCategory.HEALTHCHECK_FAILURE,
        },
        IncidentCategory.DEPENDENCY_FAILURE: {
            IncidentCategory.HTTP_5XX,
            IncidentCategory.HTTP_TIMEOUT,
            IncidentCategory.LATENCY_SLO_BREACH,
        },
        IncidentCategory.PROCESS_CRASH: {
            IncidentCategory.HTTP_5XX,
            IncidentCategory.HTTP_TIMEOUT,
            IncidentCategory.WEBSOCKET_FAILURE,
            IncidentCategory.HEALTHCHECK_FAILURE,
        },
        IncidentCategory.RESOURCE_EXHAUSTION: {
            IncidentCategory.LATENCY_SLO_BREACH,
            IncidentCategory.HTTP_TIMEOUT,
            IncidentCategory.PROCESS_CRASH,
        }
    }

    def __init__(self, temporal_window_seconds: float = 60.0):
        self.temporal_window_seconds = temporal_window_seconds
        self._correlation_groups: Dict[str, IncidentCorrelation] = {}
        self._correlated_incidents: Dict[str, str] = {}  # child_id -> primary_id

    def correlate(
        self,
        incidents: List[Incident],
        dependency_graph: Optional[Dict[str, List[str]]] = None,
    ) -> List[IncidentCorrelation]:
        """
        Groups incidents into causal correlations.
        Only links incidents if there is causal evidence or an architectural dependency relationship.
        Temporal proximity alone is insufficient for causal link.
        """
        deps = dependency_graph or {}
        sorted_incidents = sorted(incidents, key=lambda inc: inc.detection_time)

        for inc in sorted_incidents:
            matched_group_key: Optional[str] = None

            # Check existing correlation groups
            for key, group in self._correlation_groups.items():
                primary_inc = next((i for i in incidents if i.incident_id == group.primary_incident_id), None)
                if not primary_inc:
                    continue

                # Check temporal window
                dt = abs(inc.detection_time - primary_inc.detection_time)
                if dt > self.temporal_window_seconds:
                    continue

                # Causal check:
                # 1. Known causal chain between categories
                is_causal_category = (
                    primary_inc.category in self.KNOWN_CAUSAL_CHAINS
                    and inc.category in self.KNOWN_CAUSAL_CHAINS[primary_inc.category]
                )

                # 2. Dependency graph linkage: does inc.service depend on primary_inc.service?
                is_dependent_service = inc.service in deps.get(primary_inc.service, []) or primary_inc.service in deps.get(inc.service, [])

                # Strict requirement: Must have causal category match OR dependency graph edge, not just temporal closeness!
                if is_causal_category or is_dependent_service:
                    matched_group_key = key
                    break

            if matched_group_key:
                # Link as symptom/child
                group = self._correlation_groups[matched_group_key]
                if inc.incident_id not in group.correlated_incident_ids:
                    group.correlated_incident_ids.append(inc.incident_id)
                    inc.parent_incident_id = group.primary_incident_id
                    evidence_note = (
                        f"Causal link confirmed: {inc.category.value} on {inc.service} "
                        f"derived from primary {group.root_cause_service} within {dt:.1f}s"
                    )
                    group.causal_evidence.append(evidence_note)
                    self._correlated_incidents[inc.incident_id] = group.primary_incident_id
            else:
                # New root incident group
                new_key = f"corr-grp-{inc.incident_id}"
                new_group = IncidentCorrelation(
                    correlation_key=new_key,
                    primary_incident_id=inc.incident_id,
                    correlated_incident_ids=[],
                    root_cause_service=inc.service,
                    causal_evidence=[f"Root incident detected: {inc.category.value} on {inc.service}"],
                    created_at=inc.detection_time,
                )
                self._correlation_groups[new_key] = new_group

        return list(self._correlation_groups.values())

    def get_correlations(self) -> List[IncidentCorrelation]:
        return list(self._correlation_groups.values())
