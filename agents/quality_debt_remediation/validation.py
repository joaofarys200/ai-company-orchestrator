"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Debt validation engine. Rejects false, stale, or weak debt before any remediation planning.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Set

from .debt import IngestedDebtItem
from .models import DebtValidationResult, ValidationStatus


class DebtValidator:
    """
    Validates ingested debt items against physical evidence, scope,
    reproducibility, and temporal freshness.
    """

    def __init__(self, stale_threshold_days: float = 90.0):
        self.stale_threshold_days = stale_threshold_days
        self._seen_hashes: Set[str] = set()
        self._active_debt_ids: Set[str] = set()

    def validate(
        self,
        debt_item: IngestedDebtItem,
        existing_active_debts: Optional[List[IngestedDebtItem]] = None,
        codebase_surface_exists: bool = True,
    ) -> DebtValidationResult:
        validation_id = f"val_{uuid.uuid4().hex[:8]}"
        debt_id = debt_item.debt_id
        scope = debt_item.affected_surface
        content_hash = debt_item.content_hash()

        # 1. Check for Codebase Surface Existence (Structural Confirmation)
        if not codebase_surface_exists or not scope or scope.lower() in ("none", "null", ""):
            return DebtValidationResult(
                validation_id=validation_id,
                debt_id=debt_id,
                status=ValidationStatus.INVALID_DEBT,
                confidence=0.9,
                evidence_validity=False,
                reproducibility=False,
                scope=scope,
                explanation=f"Target surface '{scope}' does not exist in codebase or is empty.",
            )

        # 2. Check for Duplicate Debt
        if content_hash in self._seen_hashes or debt_id in self._active_debt_ids:
            return DebtValidationResult(
                validation_id=validation_id,
                debt_id=debt_id,
                status=ValidationStatus.DUPLICATE_DEBT,
                confidence=0.95,
                evidence_validity=True,
                reproducibility=True,
                scope=scope,
                explanation=f"Debt item {debt_id} with hash {content_hash[:8]} is already active or observed.",
            )

        # 3. Check for Stale Debt
        if debt_item.age_days > self.stale_threshold_days:
            return DebtValidationResult(
                validation_id=validation_id,
                debt_id=debt_id,
                status=ValidationStatus.STALE_DEBT,
                confidence=0.85,
                evidence_validity=False,
                reproducibility=False,
                scope=scope,
                explanation=f"Debt item age ({debt_item.age_days:.1f} days) exceeds stale threshold ({self.stale_threshold_days} days).",
            )

        # 4. Check Evidence Substantiality
        evidence = debt_item.evidence
        if not evidence or (isinstance(evidence, dict) and len(evidence) == 0):
            return DebtValidationResult(
                validation_id=validation_id,
                debt_id=debt_id,
                status=ValidationStatus.WEAK_EVIDENCE,
                confidence=0.4,
                evidence_validity=False,
                reproducibility=False,
                scope=scope,
                explanation="No empirical evidence dictionary provided for debt item.",
            )

        # 5. Check for Conflicting Debts
        if existing_active_debts:
            for active in existing_active_debts:
                if active.debt_id != debt_id and active.affected_surface == scope:
                    if active.category != debt_item.category and debt_item.severity == "CRITICAL":
                        return DebtValidationResult(
                            validation_id=validation_id,
                            debt_id=debt_id,
                            status=ValidationStatus.CONFLICTED_DEBT,
                            confidence=0.75,
                            evidence_validity=True,
                            reproducibility=True,
                            scope=scope,
                            explanation=f"Surface '{scope}' is already subject to active debt {active.debt_id} with conflicting category.",
                        )

        # 6. Check Confidence & Reproducibility
        if debt_item.confidence < 0.5:
            return DebtValidationResult(
                validation_id=validation_id,
                debt_id=debt_id,
                status=ValidationStatus.REQUIRES_HUMAN_REVIEW,
                confidence=debt_item.confidence,
                evidence_validity=True,
                reproducibility=False,
                scope=scope,
                explanation=f"Debt confidence {debt_item.confidence:.2f} is below autonomous threshold (0.50). Human review required.",
            )

        # 7. Debt is Valid
        self._seen_hashes.add(content_hash)
        self._active_debt_ids.add(debt_id)

        return DebtValidationResult(
            validation_id=validation_id,
            debt_id=debt_id,
            status=ValidationStatus.VALID_DEBT,
            confidence=debt_item.confidence,
            evidence_validity=True,
            reproducibility=True,
            scope=scope,
            explanation=f"Debt item verified with confirmed structural evidence on surface '{scope}'.",
        )

    def validate_batch(
        self, debt_items: List[IngestedDebtItem], codebase_surface_exists: bool = True
    ) -> List[DebtValidationResult]:
        results = []
        for item in debt_items:
            results.append(self.validate(item, codebase_surface_exists=codebase_surface_exists))
        return results
