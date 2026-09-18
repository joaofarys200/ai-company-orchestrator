"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: governance.py
Validates governance authority and enforces that the SOLE authorized input for
self-modification is a verified APPROVED_FOR_IMPLEMENTATION decision from Phase 64.

Strictly rejects unapproved, tentative, or incomplete proposals:
    OBSERVATION_ONLY -> REJECTED
    PROPOSAL_READY -> REJECTED
    VALIDATION_REQUIRED -> REJECTED
    HUMAN_REVIEW -> REJECTED
    BLOCKED -> REJECTED
    REJECTED -> REJECTED
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from .models import TransactionState


class GovernanceInputValidator:
    """Gatekeeper ensuring self-modification cannot occur without Phase 64 approval."""

    APPROVED_STATE = "APPROVED_FOR_IMPLEMENTATION"

    DISALLOWED_STATES = {
        "OBSERVATION_ONLY",
        "PROPOSAL_READY",
        "VALIDATION_REQUIRED",
        "HUMAN_REVIEW",
        "BLOCKED",
        "REJECTED",
    }

    REQUIRED_KEYS = [
        "problem_id",
        "alternative_id",
        "state",
        "provenance_hash",
    ]

    REQUIRED_PAYLOAD_ELEMENTS = [
        "architecture_problem",
        "selected_alternative",
        "affected_surface",
        "constraints",
        "contract_analysis",
        "behavior_analysis",
        "risk_analysis",
        "migration_plan",
        "verification_plan",
        "rollback_plan",
    ]

    def validate_governance_input(
        self,
        decision_data: Dict[str, Any],
        context_payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """Validate that the decision is explicitly APPROVED_FOR_IMPLEMENTATION and complete."""
        if not decision_data:
            return False, "GOVERNANCE_REJECTED: Missing decision data."

        state = decision_data.get("state")
        if state != self.APPROVED_STATE:
            return False, f"GOVERNANCE_REJECTED: Decision state '{state}' is not '{self.APPROVED_STATE}'."

        for req in self.REQUIRED_KEYS:
            if req not in decision_data or not decision_data[req]:
                return False, f"GOVERNANCE_REJECTED: Missing mandatory decision field '{req}'."

        # Check provenance hash
        prov_hash = decision_data.get("provenance_hash", "")
        if not prov_hash or len(prov_hash) < 16:
            return False, "GOVERNANCE_REJECTED: Invalid or missing provenance hash."

        # Verify Sentinel passed in Phase 64
        if not decision_data.get("sentinel_passed", False):
            return False, "GOVERNANCE_REJECTED: Security Sentinel failed in Phase 64 decision."

        # Verify payload completeness if context payload supplied
        if context_payload is not None:
            for element in self.REQUIRED_PAYLOAD_ELEMENTS:
                if element not in context_payload:
                    return False, f"GOVERNANCE_REJECTED: Incomplete governance payload, missing '{element}'."

        return True, "GOVERNANCE_VERIFIED: Approved for implementation."

    def compute_decision_hash(self, decision_data: Dict[str, Any]) -> str:
        """Compute SHA-256 fingerprint of governance decision."""
        canon = json.dumps(decision_data, sort_keys=True, default=str)
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()
