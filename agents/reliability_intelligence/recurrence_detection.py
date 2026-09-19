"""
Phase 72 — Incident Recurrence Detection
Integrates with Phase 71 operational and incident ledger to detect repeat failure modes.
"""

from __future__ import annotations

import collections
import time
import uuid
from typing import Any, Dict, List, Optional

from .models import (
    RecurrenceSignal,
    RecurrenceStatus,
)


class RecurrenceDetector:
    """Evaluates recurrence of incidents by category, root cause, and dependency."""

    def __init__(self, recurrence_threshold: int = 2, escalating_threshold: int = 4):
        self.recurrence_thresh = recurrence_threshold
        self.escalating_thresh = escalating_threshold

    def evaluate_from_incidents(
        self,
        service: str,
        incident_category: str,
        incident_history: List[Dict[str, Any]],
        pattern_type: str = "category",
    ) -> RecurrenceSignal:
        evidence_id = f"ev_rec_{uuid.uuid4().hex[:8]}"
        now = time.time()

        matching_incidents = [
            inc for inc in incident_history
            if inc.get("service") == service and inc.get("category", "").lower() == incident_category.lower()
        ]

        count = len(matching_incidents)
        if count == 0:
            return RecurrenceSignal(
                signal_id=f"rec_{uuid.uuid4().hex[:6]}",
                incident_category=incident_category,
                service=service,
                occurrence_count=0,
                first_seen=now,
                last_seen=now,
                status=RecurrenceStatus.UNKNOWN,
                pattern_type=pattern_type,
                evidence_ids=[evidence_id],
            )

        timestamps = [inc.get("detection_time", now) for inc in matching_incidents]
        first_t = min(timestamps)
        last_t = max(timestamps)
        evidence_ids = [inc.get("evidence", f"ev_{i}") for i, inc in enumerate(matching_incidents)]

        if count == 1:
            status = RecurrenceStatus.FIRST_OCCURRENCE
        elif count >= self.escalating_thresh:
            status = RecurrenceStatus.ESCALATING_RECURRENCE
        elif count >= self.recurrence_thresh:
            status = RecurrenceStatus.RECURRENT
        else:
            status = RecurrenceStatus.FIRST_OCCURRENCE

        return RecurrenceSignal(
            signal_id=f"rec_{uuid.uuid4().hex[:6]}",
            incident_category=incident_category,
            service=service,
            occurrence_count=count,
            first_seen=first_t,
            last_seen=last_t,
            status=status,
            pattern_type=pattern_type,
            evidence_ids=evidence_ids,
        )
