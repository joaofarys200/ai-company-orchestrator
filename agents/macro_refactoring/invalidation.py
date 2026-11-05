"""
JARVIS OS — Phase 73: Autonomous Macro-Refactoring Engine
Module: invalidation.py
Dependency-aware evidence invalidation tracker. Enforces the invariant:
No accepted step may silently depend on invalidated or stale evidence.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, List, Set, Tuple

from .graph import MigrationGraph
from .models import (
    EvidenceRecord,
    InvalidationRecord,
    MacroMigration,
    MigrationStep,
    StepState,
)


class EvidenceInvalidator:
    """
    Tracks and executes dependency-aware invalidation of evidence records
    when an upstream migration step alters code, interfaces, or assumptions.
    """

    def invalidate_downstream_evidence(
        self,
        migration: MacroMigration,
        mutating_step_id: str,
        reason: str,
    ) -> List[InvalidationRecord]:
        """
        Calculates all downstream dependents of `mutating_step_id`.
        For each downstream step with accepted evidence:
        1. Invalids evidence in the evidence ledger.
        2. Demotes step state from ACCEPTED to INVALIDATED.
        3. Appends an InvalidationRecord to the migration audit trail.
        """
        graph = MigrationGraph(migration.steps)
        downstream_ids = graph.get_downstream_dependents(mutating_step_id)

        invalidation_records: List[InvalidationRecord] = []
        mutating_step = migration.steps.get(mutating_step_id)
        affected_files_desc = ", ".join(mutating_step.affected_files) if mutating_step else "unknown"

        for step_id in sorted(downstream_ids):
            step = migration.steps.get(step_id)
            if not step:
                continue

            # Check if this step had evidence or was accepted
            needs_invalidation = False
            for ev_ref in list(step.evidence_refs):
                for ev in migration.evidence_ledger:
                    if ev.evidence_id == ev_ref and ev.valid:
                        ev.valid = False
                        ev.invalidation_reason = (
                            f"Invalidated by mutation in upstream step '{mutating_step_id}' "
                            f"(files: {affected_files_desc}): {reason}"
                        )
                        needs_invalidation = True

                        rec = InvalidationRecord(
                            invalidation_id=f"inv_{uuid.uuid4().hex[:8]}",
                            triggered_by_step_id=mutating_step_id,
                            invalidated_step_id=step_id,
                            evidence_id=ev.evidence_id,
                            reason=ev.invalidation_reason,
                            timestamp=time.time(),
                        )
                        invalidation_records.append(rec)
                        migration.invalidations.append(rec)

            if needs_invalidation or step.state == StepState.ACCEPTED:
                step.state = StepState.INVALIDATED
                # Demote current migration progress if it was completed
                if migration.status == "COMPLETED":
                    migration.status = "EXECUTING"

        return invalidation_records

    def check_evidence_freshness(self, migration: MacroMigration) -> Tuple[bool, List[str]]:
        """
        Verifies that all evidence required by accepted steps remains valid.
        Returns (is_fresh, list_of_stale_reasons).
        """
        stale_reasons: List[str] = []

        for step_id, step in migration.steps.items():
            if step.state == StepState.INVALIDATED:
                stale_reasons.append(f"Step '{step_id}' is in INVALIDATED state due to upstream mutation.")
            elif step.state == StepState.ACCEPTED:
                if not step.evidence_refs:
                    stale_reasons.append(f"Step '{step_id}' is marked ACCEPTED but has no evidence records.")
                    continue

                for ref in step.evidence_refs:
                    ev = next((e for e in migration.evidence_ledger if e.evidence_id == ref), None)
                    if not ev:
                        stale_reasons.append(f"Step '{step_id}' references missing evidence '{ref}'.")
                    elif not ev.valid:
                        stale_reasons.append(
                            f"Step '{step_id}' relies on invalidated evidence '{ref}': {ev.invalidation_reason}"
                        )

        return (len(stale_reasons) == 0, stale_reasons)
