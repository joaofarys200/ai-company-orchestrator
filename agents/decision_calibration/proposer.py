"""
JARVIS OS — Phase 41: Autonomous Decision Calibration & Failure Intelligence
Policy Proposal Engine: Deterministic Formulation of Policy Improvements.

Principles:
- Proposals are synthesized strictly from empirical DecisionOutcome error analysis.
- Prohibited operations (disabling security, bypassing gates) are permanently rejected.
- Proposals never self-activate; they require explicit human review and registration.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from agents.decision_calibration.models import (
    PROHIBITED_POLICY_OPERATIONS,
    DecisionCorrectness,
    DecisionErrorTaxonomy,
    DecisionOutcome,
    PolicyChangeProposal,
    PolicyChangeType,
    PolicyStatus,
)


class PolicyProposalEngine:
    """
    Formulates structured, versioned proposals to refine policy rules based on
    classified decision outcomes, while guarding against unsafe modifications.
    """

    @classmethod
    def formulate_proposal_from_outcome(
        cls,
        outcome: DecisionOutcome,
        current_version: str = "40.1.0",
        proposed_version: str = "41.0.0",
    ) -> Optional[PolicyChangeProposal]:
        """
        Formulates a policy refinement proposal if the outcome indicates a POLICY_GAP,
        OBSERVATION_GAP, or POLICY_PRIORITY_ERROR.
        """
        if outcome.decision_correctness == DecisionCorrectness.CORRECT:
            return None

        proposal_id = f"prop_{outcome.cycle_id}_{int(time.time()*1000) % 100000}"

        if outcome.root_cause == DecisionErrorTaxonomy.OBSERVATION_GAP:
            return PolicyChangeProposal(
                proposal_id=proposal_id,
                source_outcome_id=outcome.outcome_id,
                current_policy_version=current_version,
                proposed_policy_version=proposed_version,
                change_type=PolicyChangeType.REFINE_CONDITION,
                affected_rules=["RULE_03_OSCILLATION_DETECTED"],
                old_conditions="ctx.oscillation_status == OscillationStatus.CONFIRMED_OSCILLATION",
                new_conditions="ctx.oscillation_status == OscillationStatus.CONFIRMED_OSCILLATION or ctx.loop_state.oscillation_status == OscillationStatus.CONFIRMED_OSCILLATION",
                expected_benefit="Guarantees oscillation history recorded in previous cycle is evaluated before deciding next step, eliminating observation gap in Decision #191.",
                possible_regression="None. Security Sentinel and Finish Gate invariants are untouched.",
                evidence_refs=outcome.evidence_ids or ["EVD_OSC_DEFENSE_01"],
                confidence=0.98,
                requires_human_review=True,
                status=PolicyStatus.PROPOSED,
            )

        elif outcome.root_cause == DecisionErrorTaxonomy.POLICY_GAP:
            return PolicyChangeProposal(
                proposal_id=proposal_id,
                source_outcome_id=outcome.outcome_id,
                current_policy_version=current_version,
                proposed_policy_version=proposed_version,
                change_type=PolicyChangeType.REFINE_CONDITION,
                affected_rules=[outcome.rule_id],
                old_conditions="Current rule conditions were insufficient to match observed failure.",
                new_conditions="Add explicit matching for observed discrepancy and route to proper recovery stage.",
                expected_benefit=f"Eliminates unhandled discrepancy in rule {outcome.rule_id}.",
                possible_regression="Low. Affects only targeted failure path.",
                evidence_refs=outcome.evidence_ids,
                confidence=0.92,
                requires_human_review=True,
                status=PolicyStatus.PROPOSED,
            )

        elif outcome.root_cause == DecisionErrorTaxonomy.POLICY_PRIORITY_ERROR:
            return PolicyChangeProposal(
                proposal_id=proposal_id,
                source_outcome_id=outcome.outcome_id,
                current_policy_version=current_version,
                proposed_policy_version=proposed_version,
                change_type=PolicyChangeType.CHANGE_PRIORITY,
                affected_rules=[outcome.rule_id],
                old_conditions="Conflicting rule had higher priority than recovery rule.",
                new_conditions="Elevate recovery rule priority above default progression.",
                expected_benefit="Ensures safety/recovery rule takes precedence when both conditions are active.",
                possible_regression="Requires regression suite run in sandbox before approval.",
                evidence_refs=outcome.evidence_ids,
                confidence=0.90,
                requires_human_review=True,
                status=PolicyStatus.PROPOSED,
            )

        return None

    @classmethod
    def validate_safety_invariants(cls, proposal: PolicyChangeProposal) -> tuple[bool, str]:
        """
        Validates that the proposal does not attempt to bypass security or gates.
        """
        is_safe, reason = proposal.validate_prohibited_operations()
        if not is_safe:
            return False, reason

        # Check for banned substrings
        combined_text = f"{proposal.old_conditions} {proposal.new_conditions} {proposal.change_type.value}".upper()
        for banned in PROHIBITED_POLICY_OPERATIONS:
            if banned in combined_text:
                return False, f"Permanent safety block: {banned} cannot be proposed."

        return True, "Proposal complies with all safety invariants."
