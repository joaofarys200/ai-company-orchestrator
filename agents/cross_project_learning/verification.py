"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: verification.py
Verification knowledge transfer integrating Phase 62 Continuous Verification.
Produces test selection hints, risk boundary probes, and invariant checks.

Strict Invariant:
    EXTERNAL_PATTERN → TEST_SELECTION_HINT
    NEVER: EXTERNAL_PATTERN → VERIFIED
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from .models import EngineeringKnowledgeItem, ProjectFingerprint


class VerificationKnowledgeTransferEngine:
    """Provides advisory verification hints to Phase 62 without bypassing local evidence gates."""

    @classmethod
    def generate_verification_hints(
        cls,
        knowledge_item: EngineeringKnowledgeItem,
        target_fingerprint: ProjectFingerprint,
    ) -> Dict[str, Any]:
        """Produce advisory test selection and boundary exploration hints."""
        category = knowledge_item.category
        pattern = knowledge_item.pattern

        hints: List[str] = []
        target_boundaries: List[str] = []

        if category.value == "TEST_PATTERN":
            hints.append(f"Prioritize tests exercising invariant: '{pattern.get('target_invariant', '')}'")
            target_boundaries.append("unit_invariant_boundary")
        elif category.value == "RISK_PATTERN":
            hints.append(f"Explore risk surface: '{pattern.get('risk_class', '')}' with fault injection")
            target_boundaries.append(f"risk_{pattern.get('risk_class', '')}_boundary")
        elif category.value == "CONTRACT_PATTERN":
            hints.append(f"Observe contract protocol '{pattern.get('protocol', '')}' against drift")
            target_boundaries.append("api_contract_boundary")
        elif category.value == "BEHAVIOR_PATTERN":
            hints.append(f"Validate FSM transitions for '{pattern.get('state_machine', '')}'")
            target_boundaries.append("state_machine_boundary")
        elif category.value == "FAILURE_PATTERN":
            hints.append(f"Check for regression symptom: '{pattern.get('symptom', '')}'")
            target_boundaries.append("failure_symptom_boundary")
        else:
            hints.append(f"Advisory check for {category.value} pattern '{pattern.get('name', '')}'")

        return {
            "source_knowledge_id": knowledge_item.knowledge_id,
            "target_project_id": target_fingerprint.project_id,
            "category": category.value,
            "advisory_hints": hints,
            "target_boundaries": target_boundaries,
            "verification_rule": "ADVISORY_HINT_ONLY_LOCAL_EVIDENCE_MANDATORY",
            "cannot_grant_verification": True,
        }
