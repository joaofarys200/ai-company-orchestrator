"""
JARVIS OS — Phase 78: Autonomous Causal Diagnosis & Root-Cause Analysis
Module: adapters.py
Subsystem adapters connecting causal diagnosis to Phases 71, 72, 73, 76, and 77.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .graph import CausalGraphBuilder
from .models import CausalNodeType, TimelineEvent
from .timeline import TimelineReconstructor


class Phase71IncidentAdapter:
    """Adapts Phase 71 incidents into causal timeline events and graph symptom nodes."""

    @staticmethod
    def ingest_incident(
        incident_id: str,
        service: str,
        category: str,
        description: str,
        detection_time: float,
        timeline: TimelineReconstructor,
        graph: CausalGraphBuilder,
    ) -> str:
        timeline.add_event(
            event_id=f"ev_inc_{incident_id}",
            subsystem=service,
            event_type="INCIDENT_SYMPTOM",
            description=f"[{category}] {description}",
            timestamp=detection_time,
        )
        symptom_node_id = f"node_symptom_{incident_id}"
        graph.add_node(
            node_id=symptom_node_id,
            node_type=CausalNodeType.OBSERVABLE_SYMPTOM,
            description=f"[{category}] {description}",
            subsystem=service,
            timestamp=detection_time,
        )
        return symptom_node_id


class Phase72ReliabilityAdapter:
    """Adapts Phase 72 anomaly and capacity signals into environmental timeline events."""

    @staticmethod
    def ingest_signal(
        signal_id: str,
        service: str,
        signal_type: str,
        details: str,
        timestamp: float,
        timeline: TimelineReconstructor,
        graph: CausalGraphBuilder,
    ) -> str:
        timeline.add_event(
            event_id=f"ev_sig_{signal_id}",
            subsystem=service,
            event_type="RELIABILITY_SIGNAL",
            description=f"[{signal_type}] {details}",
            timestamp=timestamp,
        )
        node_id = f"node_signal_{signal_id}"
        graph.add_node(
            node_id=node_id,
            node_type=CausalNodeType.CONTRIBUTING_FACTOR,
            description=f"[{signal_type}] {details}",
            subsystem=service,
            timestamp=timestamp,
        )
        return node_id


class Phase73RefactoringAdapter:
    """Adapts Phase 73 migration step failures into candidate root cause nodes."""

    @staticmethod
    def ingest_step_failure(
        step_id: str,
        migration_id: str,
        reason: str,
        timestamp: float,
        timeline: TimelineReconstructor,
        graph: CausalGraphBuilder,
    ) -> str:
        timeline.add_event(
            event_id=f"ev_step_{step_id}",
            subsystem="macro_refactoring",
            event_type="STEP_FAILURE",
            description=f"Migration '{migration_id}' step '{step_id}' failed: {reason}",
            timestamp=timestamp,
        )
        node_id = f"node_rc_{step_id}"
        graph.add_node(
            node_id=node_id,
            node_type=CausalNodeType.ROOT_CAUSE,
            description=f"Failed migration step '{step_id}': {reason}",
            subsystem="macro_refactoring",
            timestamp=timestamp,
        )
        return node_id


class Phase77EvidenceAdapter:
    """Interacts with Phase 77 evidence governance to check artifact verification status."""

    @staticmethod
    def filter_active_evidence(evidence_refs: List[str], stale_refs: Optional[List[str]] = None) -> List[str]:
        stale_set = set(stale_refs or [])
        return [r for r in evidence_refs if r not in stale_set]
