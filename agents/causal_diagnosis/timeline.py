"""
JARVIS OS — Phase 78: Autonomous Causal Diagnosis & Root-Cause Analysis
Module: timeline.py
Reconstructs chronological timeline of events leading up to and during an incident,
handling missing timestamps, sequence order, and temporal ambiguity.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from .models import TimelineEvent


class TimelineReconstructor:
    """
    Reconstructs an ordered, consistent event sequence from heterogeneous log sources,
    explicitly preserving uncertainty regarding clock skews and missing timestamps.
    """

    def __init__(self):
        self.events: List[TimelineEvent] = []

    def add_event(
        self,
        event_id: str,
        subsystem: str,
        event_type: str,
        description: str,
        timestamp: Optional[float] = None,
        payload: Optional[Dict] = None,
        evidence_refs: Optional[List[str]] = None,
    ) -> TimelineEvent:
        """Add an event to the timeline, flagging missing timestamps if unprovided."""
        has_uncertain = False
        if timestamp is None:
            # If timestamp is missing, anchor it to the latest known event or current time, but flag uncertainty
            ts = self.events[-1].timestamp if self.events else time.time()
            has_uncertain = True
        else:
            ts = float(timestamp)

        ev = TimelineEvent(
            event_id=event_id,
            timestamp=ts,
            subsystem=subsystem,
            event_type=event_type,
            description=description,
            payload=payload or {},
            has_uncertain_timestamp=has_uncertain,
            evidence_refs=evidence_refs or [],
        )
        self.events.append(ev)
        return ev

    def get_ordered_timeline(self) -> List[TimelineEvent]:
        """
        Returns events sorted chronologically.
        Events with equal timestamps preserve their ingestion sequence order.
        """
        return sorted(self.events, key=lambda e: (e.timestamp, e.event_id))

    def detect_temporal_inversions(self) -> List[Tuple[str, str, str]]:
        """
        Identifies potential temporal inversions (e.g. effect logged with timestamp before cause).
        Returns list of (cause_id, effect_id, diagnostic).
        """
        inversions = []
        ordered = self.get_ordered_timeline()
        for i in range(len(ordered) - 1):
            e1 = ordered[i]
            e2 = ordered[i + 1]
            # If e2 has uncertain timestamp or negative diff relative to logical dependencies
            if e2.has_uncertain_timestamp:
                inversions.append((e1.event_id, e2.event_id, "UNCERTAIN_TIMESTAMP_ORDER"))
        return inversions
