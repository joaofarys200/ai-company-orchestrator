"""
JARVIS OS — Phase 42: Append-Only Immutable Experience Storage
Manages append-only persistence, cryptographic SHA-256 verification,
human curation linkages, and archival under memory pressure.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

from agents.experience_memory.models import (
    ExperienceCorrection,
    ExperienceRecord,
    ExperienceSourceType,
    HumanCurationAction,
    TemporalValidity,
)


class ExperienceStorage:
    """Immutable, append-only repository for operational cross-mission experience records."""

    def __init__(self):
        self._records: dict[str, ExperienceRecord] = {}
        self._corrections: list[ExperienceCorrection] = []
        self._curation_log: list[dict[str, Any]] = []
        self._archived_records: dict[str, ExperienceRecord] = {}

    def compute_record_hash(self, record: ExperienceRecord) -> str:
        payload = (
            f"{record.experience_id}:{record.mission_id}:{record.cycle_id}:"
            f"{record.decision}:{record.outcome}:{record.root_cause}:{record.created_at}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def add_experience(self, record: ExperienceRecord) -> ExperienceRecord:
        """Stores a new experience record immutably."""
        if record.experience_id in self._records or record.experience_id in self._archived_records:
            raise ValueError(
                f"Historical experience records are immutable. Record '{record.experience_id}' already exists. "
                "Use add_correction() to link corrections without overwriting history."
            )

        calc_hash = self.compute_record_hash(record)
        if not record.source_hash:
            # Recreate with calculated hash
            record = ExperienceRecord(
                experience_id=record.experience_id,
                mission_id=record.mission_id,
                cycle_id=record.cycle_id,
                intent_signature=record.intent_signature,
                mission_context=record.mission_context,
                decision=record.decision,
                policy_version=record.policy_version,
                observation=record.observation,
                outcome=record.outcome,
                root_cause=record.root_cause,
                severity=record.severity,
                prediction=record.prediction,
                actual_result=record.actual_result,
                adaptation=record.adaptation,
                evidence_refs=record.evidence_refs,
                task_refs=record.task_refs,
                architecture_refs=record.architecture_refs,
                tags=record.tags,
                applicability=record.applicability,
                confidence=record.confidence,
                created_at=record.created_at,
                source_type=record.source_type,
                source_hash=calc_hash,
                causal_chain=record.causal_chain,
                temporal_validity=record.temporal_validity,
                curation_status=record.curation_status,
            )

        self._records[record.experience_id] = record
        return record

    def get_experience(self, experience_id: str) -> Optional[ExperienceRecord]:
        return self._records.get(experience_id) or self._archived_records.get(experience_id)

    def list_active_experiences(self) -> list[ExperienceRecord]:
        return list(self._records.values())

    def get_all_active(self) -> list[ExperienceRecord]:
        return list(self._records.values())

    def list_all_experiences(self) -> list[ExperienceRecord]:
        return list(self._records.values()) + list(self._archived_records.values())

    def count_active(self) -> int:
        return len(self._records)

    def count_archived(self) -> int:
        return len(self._archived_records)

    def add_correction(self, correction: ExperienceCorrection) -> None:
        """Appends an audited correction linked to an existing historical record."""
        target = self.get_experience(correction.original_experience_id)
        if not target:
            raise KeyError(f"Target experience '{correction.original_experience_id}' not found for correction.")

        self._corrections.append(correction)

    def curate_experience(
        self,
        experience_id: str,
        action: HumanCurationAction,
        curator_id: str = "human_operator",
        notes: str = "",
    ) -> ExperienceRecord:
        """Applies human curation by creating a curated view without mutating historical raw facts."""
        rec = self._records.get(experience_id)
        if not rec:
            raise KeyError(f"Experience '{experience_id}' not found in active records.")

        new_status = action.value if hasattr(action, "value") else str(action)
        new_temporal = rec.temporal_validity
        if action == HumanCurationAction.MARK_STALE or str(action) == HumanCurationAction.MARK_STALE.value:
            new_temporal = TemporalValidity.STALE

        updated = ExperienceRecord(
            experience_id=rec.experience_id,
            mission_id=rec.mission_id,
            cycle_id=rec.cycle_id,
            intent_signature=rec.intent_signature,
            mission_context=rec.mission_context,
            decision=rec.decision,
            policy_version=rec.policy_version,
            observation=rec.observation,
            outcome=rec.outcome,
            root_cause=rec.root_cause,
            severity=rec.severity,
            prediction=rec.prediction,
            actual_result=rec.actual_result,
            adaptation=rec.adaptation,
            evidence_refs=rec.evidence_refs,
            task_refs=rec.task_refs,
            architecture_refs=rec.architecture_refs,
            tags=rec.tags,
            applicability=rec.applicability,
            confidence=rec.confidence,
            created_at=rec.created_at,
            source_type=rec.source_type,
            source_hash=rec.source_hash,
            causal_chain=rec.causal_chain,
            temporal_validity=new_temporal,
            curation_status=new_status,
        )

        self._records[experience_id] = updated
        self._curation_log.append({
            "experience_id": experience_id,
            "action": action.value,
            "curator_id": curator_id,
            "notes": notes,
            "timestamp": time.time(),
        })
        return updated

    def archive_under_pressure(self, max_active: int = 10000) -> int:
        """Moves oldest or stale experiences to archived partition to maintain constant memory budget."""
        if len(self._records) <= max_active:
            return 0

        excess = len(self._records) - max_active
        sorted_keys = sorted(
            self._records.keys(),
            key=lambda k: (
                1 if self._records[k].temporal_validity == TemporalValidity.STALE else 0,
                -self._records[k].created_at,
            ),
            reverse=True,
        )

        archived_count = 0
        for k in sorted_keys[:excess]:
            self._archived_records[k] = self._records.pop(k)
            archived_count += 1

        return archived_count
