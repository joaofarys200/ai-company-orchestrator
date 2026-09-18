"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: validator.py
Validator for cross-project learning integrity and governance invariant enforcement.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import (
    EngineeringKnowledgeItem,
    KnowledgeState,
    KnowledgeTransferDecision,
    LocalValidationResult,
    ProjectFingerprint,
    TransferDecisionState,
)


class CrossProjectValidator:
    """Validates structural integrity and strict adherence to governance invariants."""

    @classmethod
    def validate_fingerprint(cls, fp: ProjectFingerprint) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not fp.project_id:
            errors.append("Missing project_id in fingerprint")
        if not fp.fingerprint_hash:
            errors.append("Missing deterministic fingerprint_hash")
        if not fp.languages:
            errors.append("Fingerprint must declare at least one language")
        return len(errors) == 0, errors

    @classmethod
    def validate_knowledge_item(cls, item: EngineeringKnowledgeItem) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not item.knowledge_id:
            errors.append("Missing knowledge_id")
        if not item.source_project_id:
            errors.append("Missing source_project_id")
        if not (0.0 <= item.confidence <= 1.0):
            errors.append(f"Confidence {item.confidence} out of range [0.0, 1.0]")
        if not item.provenance or not item.provenance.source_project_id:
            errors.append("Invalid or missing provenance lineage")

        # Invariant check: Cannot be TRANSFERABLE while provenance is unvalidated
        if item.state == KnowledgeState.TRANSFERABLE and not item.evidence_scope:
            errors.append("Item cannot be TRANSFERABLE without evidence_scope")

        return len(errors) == 0, errors

    @classmethod
    def validate_transfer_decision(cls, dec: KnowledgeTransferDecision) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not dec.decision_id:
            errors.append("Missing decision_id")
        if not dec.target_project_id:
            errors.append("Missing target_project_id")

        # Core Invariant: If accepted, local validation plan MUST be present
        if dec.state not in (TransferDecisionState.REJECT_TRANSFER, TransferDecisionState.HUMAN_REVIEW):
            plan = dec.local_validation_plan
            if not plan or not plan.get("required_local_validation"):
                errors.append(
                    f"INVARIANT VIOLATION: Transfer state {dec.state.value} must have an active local validation plan!"
                )

        return len(errors) == 0, errors

    @classmethod
    def validate_local_evidence(cls, val: LocalValidationResult) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not val.validation_id:
            errors.append("Missing validation_id")
        if val.validated and not val.evidence:
            errors.append("INVARIANT VIOLATION: Cannot declare validated=True without local evidence!")
        return len(errors) == 0, errors
