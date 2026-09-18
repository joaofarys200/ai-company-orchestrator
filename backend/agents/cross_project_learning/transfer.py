"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: transfer.py
Governance engine for engineering knowledge transfer.
Guarantees that no external knowledge is promoted without local validation.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .models import (
    ApplicabilityResult,
    ApplicabilityStatus,
    CandidateKnowledge,
    KnowledgeCategory,
    KnowledgeTransferDecision,
    ProjectFingerprint,
    TransferDecisionState,
    TransferPolicyName,
)


class TransferGovernanceEngine:
    """Governs transfer proposals, enforcing validation boundaries and policy constraints."""

    @classmethod
    def decide_transfer(
        cls,
        candidate: CandidateKnowledge,
        applicability: ApplicabilityResult,
        target_fingerprint: ProjectFingerprint,
        policy: TransferPolicyName = TransferPolicyName.STANDARD,
    ) -> KnowledgeTransferDecision:
        """
        Formulate a formal transfer decision.
        Invariant: All accepted transfers require a mandatory local_validation_plan.
        """
        item = candidate.item
        dec_id = f"dec_trans_{uuid.uuid4().hex[:8]}"
        now = time.time()

        # Incompatible items are rejected immediately
        if applicability.status == ApplicabilityStatus.INCOMPATIBLE:
            return KnowledgeTransferDecision(
                decision_id=dec_id,
                state=TransferDecisionState.REJECT_TRANSFER,
                target_project_id=target_fingerprint.project_id,
                item_id=item.knowledge_id,
                category=item.category,
                rationale=f"Transfer rejected due to structural incompatibility: {'; '.join(applicability.why_not_applicable)}",
                local_validation_plan={},
                requires_human_review=False,
                confidence=applicability.confidence,
                timestamp=now,
            )

        # High-risk items or strict policies requiring human review
        requires_review = False
        if policy == TransferPolicyName.STRICT or policy == TransferPolicyName.SECURITY_FIRST:
            if applicability.confidence < 0.70 or applicability.adapter_needed:
                requires_review = True
        elif applicability.status == ApplicabilityStatus.CONTEXT_REQUIRED and applicability.adapter_needed:
            # Cross-language or unadapted contracts need review if confidence is low
            if applicability.confidence < 0.50:
                requires_review = True

        # Map to specific transfer channel
        state: TransferDecisionState
        validation_plan: Dict[str, Any] = {
            "required_local_validation": True,
            "target_project": target_fingerprint.project_id,
            "source_knowledge_id": item.knowledge_id,
            "category": item.category.value,
        }

        if item.category == KnowledgeCategory.TEST_PATTERN:
            state = TransferDecisionState.TRANSFER_TO_TEST_GENERATION
            validation_plan["validation_method"] = "PHASE_61_SYNTHESIS_AND_EXECUTION"
            validation_plan["target_invariant"] = item.pattern.get("target_invariant", "unknown_invariant")
            validation_plan["test_generation_scope"] = [f"test_{item.knowledge_id.lower()}"]
        elif item.category in (KnowledgeCategory.RISK_PATTERN, KnowledgeCategory.FAILURE_PATTERN):
            state = TransferDecisionState.TRANSFER_TO_RISK_MODEL
            validation_plan["validation_method"] = "PHASE_62_CONTINUOUS_VERIFICATION_HINT"
            validation_plan["risk_class"] = item.pattern.get("risk_class", "unknown_risk")
        elif item.category in (KnowledgeCategory.REPAIR_PATTERN, KnowledgeCategory.RECOVERY_PATTERN):
            state = TransferDecisionState.TRANSFER_TO_REPAIR_SEARCH
            validation_plan["validation_method"] = "PHASE_54_VERIFIED_REPAIR_PROOF"
            validation_plan["failure_signature"] = item.pattern.get("failure_signature", "unknown_sig")
        elif applicability.adapter_needed:
            state = TransferDecisionState.TRANSFER_AS_HYPOTHESIS
            validation_plan["validation_method"] = "CROSS_LANGUAGE_SEMANTIC_ADAPTER"
            validation_plan["adapter_target"] = applicability.target_language
        elif applicability.status == ApplicabilityStatus.DIRECTLY_APPLICABLE:
            state = TransferDecisionState.TRANSFER_FOR_CONSIDERATION
            validation_plan["validation_method"] = "LOCAL_INVARIANT_ASSERTION"
        else:
            state = TransferDecisionState.TRANSFER_AS_HYPOTHESIS
            validation_plan["validation_method"] = "EXPLORATORY_HYPOTHESIS_TESTING"

        if requires_review:
            state = TransferDecisionState.HUMAN_REVIEW

        rationale = (
            f"Transferred as {state.value} under {policy.value} policy. "
            f"Applicability: {applicability.status.value} (conf={applicability.confidence:.2f}). "
            f"Reasons: {'; '.join(applicability.why_applicable[:2])}."
        )

        return KnowledgeTransferDecision(
            decision_id=dec_id,
            state=state,
            target_project_id=target_fingerprint.project_id,
            item_id=item.knowledge_id,
            category=item.category,
            rationale=rationale,
            local_validation_plan=validation_plan,
            requires_human_review=requires_review,
            confidence=applicability.confidence,
            timestamp=now,
        )
