"""
Release Gate Governance Module
Phase 70 — Autonomous Release Readiness & Production Governance

Central decision synthesis engine. Combines all domain evaluations,
risk models, blocker checks, and human review tickets into a tamper-evident ReleaseGateDecision.
"""

from __future__ import annotations
import uuid
import time
from typing import Dict, Any, List, Optional
from .models import (
    ReleaseGateDecision, ReleaseGateDecisionState, ReleaseBlocker,
    HumanReviewTicket, BlockerCategory
)
from .risk import ReleaseRiskModel
from .policy import ReleasePolicyEngine, ReleasePolicyLevel
from .provenance import ReleaseProvenanceTracker


class ReleaseGateGovernance:
    """The central release authority synthesizing domain evaluations into a release gate verdict."""

    @classmethod
    def evaluate_candidate(
        cls,
        candidate_id: str,
        security_summary: Dict[str, Any],
        quality_summary: Dict[str, Any],
        debt_summary: Dict[str, Any],
        architecture_summary: Dict[str, Any],
        contract_summary: Dict[str, Any],
        behavior_summary: Dict[str, Any],
        performance_summary: Dict[str, Any],
        runtime_summary: Dict[str, Any],
        observability_summary: Dict[str, Any],
        dependency_summary: Dict[str, Any],
        configuration_summary: Dict[str, Any],
        rollback_summary: Dict[str, Any],
        deployment_available: bool = False,
        policy_level: ReleasePolicyLevel = ReleasePolicyLevel.GOVERNED,
        decision_id: Optional[str] = None
    ) -> ReleaseGateDecision:
        """
        Synthesizes multi-domain evaluations into a comprehensive ReleaseGateDecision.
        """
        d_id = decision_id or f"gate-dec-{uuid.uuid4().hex[:12]}"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Collect all blockers across domains
        all_blockers: List[ReleaseBlocker] = []
        for domain in [
            security_summary, quality_summary, debt_summary,
            architecture_summary, contract_summary, behavior_summary,
            performance_summary, runtime_summary, observability_summary,
            dependency_summary, configuration_summary, rollback_summary
        ]:
            if "blockers" in domain:
                all_blockers.extend(domain["blockers"])

        # Collect all human review triggers
        review_reasons: List[str] = []
        for domain_name, domain in [
            ("security", security_summary),
            ("quality", quality_summary),
            ("debt", debt_summary),
            ("architecture", architecture_summary),
            ("contract", contract_summary),
            ("behavior", behavior_summary),
            ("performance", performance_summary),
            ("runtime", runtime_summary),
            ("observability", observability_summary),
            ("dependency", dependency_summary),
            ("configuration", configuration_summary),
            ("rollback", rollback_summary)
        ]:
            if domain.get("requires_human_review"):
                for r in domain.get("review_reasons", []):
                    review_reasons.append(f"[{domain_name.upper()}] {r}")

        # Construct multi-dimensional risk vector
        risk_vector = ReleaseRiskModel.calculate_vector(
            security_summary=security_summary,
            quality_summary=quality_summary,
            architecture_summary=architecture_summary,
            behavior_summary=behavior_summary,
            contract_summary=contract_summary,
            performance_summary=performance_summary,
            runtime_summary=runtime_summary,
            configuration_summary=configuration_summary,
            dependency_summary=dependency_summary,
            rollback_summary=rollback_summary,
            observability_summary=observability_summary
        )

        has_risks = any(
            item.value > 0.25 for item in risk_vector.dimensions.values()
        ) or quality_summary.get("accepted_with_debt", False) or debt_summary.get("accepted_with_debt", False) or debt_summary.get("deferred_debt_count", 0) > 0

        # Evaluate policy engine
        policy_engine = ReleasePolicyEngine(policy_level)
        decision_state = policy_engine.evaluate_decision_state(
            blockers=all_blockers,
            human_review_required=(len(review_reasons) > 0),
            deployment_available=deployment_available,
            has_risks=has_risks
        )

        # Generate human review ticket if state is HUMAN_REVIEW
        ticket: Optional[HumanReviewTicket] = None
        if decision_state == ReleaseGateDecisionState.HUMAN_REVIEW:
            ticket = HumanReviewTicket(
                ticket_id=f"ticket-hr-{uuid.uuid4().hex[:10]}",
                candidate_id=candidate_id,
                reason="; ".join(review_reasons),
                evidence={
                    "review_reasons": review_reasons,
                    "risk_vector": risk_vector.to_dict(),
                    "blocker_count": len(all_blockers)
                },
                timeout_seconds=3600.0,
                created_at=now,
                status="PENDING"
            )

        domain_summaries = {
            "security": security_summary,
            "quality": quality_summary,
            "debt": debt_summary,
            "architecture": architecture_summary,
            "contract": contract_summary,
            "behavior": behavior_summary,
            "performance": performance_summary,
            "runtime": runtime_summary,
            "observability": observability_summary,
            "dependency": dependency_summary,
            "configuration": configuration_summary,
            "rollback": rollback_summary
        }

        evidence_ledger = [
            {"domain": k, "summary": v.get("status") or v.get("verdict") or v.get("classification")}
            for k, v in domain_summaries.items()
        ]

        allowed_to_release = (decision_state in [
            ReleaseGateDecisionState.RELEASE_READY,
            ReleaseGateDecisionState.RELEASE_READY_WITH_RISK
        ])

        payload_for_provenance = {
            "decision_id": d_id,
            "candidate_id": candidate_id,
            "state": decision_state.value,
            "risk_vector": risk_vector.to_dict(),
            "blockers": [b.to_dict() for b in all_blockers],
            "allowed_to_release": allowed_to_release,
            "evaluated_at": now
        }
        provenance_hash = ReleaseProvenanceTracker.compute_sha256(payload_for_provenance)

        return ReleaseGateDecision(
            decision_id=d_id,
            candidate_id=candidate_id,
            state=decision_state,
            risk_vector=risk_vector,
            blockers=all_blockers,
            human_review_ticket=ticket,
            domain_summaries=domain_summaries,
            evidence_ledger=evidence_ledger,
            provenance_hash=provenance_hash,
            evaluated_at=now,
            allowed_to_release=allowed_to_release
        )

    @classmethod
    def resolve_human_review(
        cls,
        decision: ReleaseGateDecision,
        approved: bool,
        notes: str = "",
        timed_out: bool = False
    ) -> ReleaseGateDecision:
        """
        Resolves a pending human review ticket.
        Rule: If timed out, state transitions to BLOCKED.
        """
        if not decision.human_review_ticket:
            return decision

        ticket = decision.human_review_ticket
        if timed_out:
            ticket.status = "TIMED_OUT"
            ticket.decision_notes = f"Timeout reached. Automatic transition to BLOCKED. {notes}".strip()
            decision.state = ReleaseGateDecisionState.BLOCKED
            decision.allowed_to_release = False
            decision.blockers.append(ReleaseBlocker(
                blocker_id=f"blocker-hr-timeout-{ticket.ticket_id}",
                category=BlockerCategory.MISSING_MANDATORY_EVIDENCE,
                description="Human review ticket timed out without signoff; release blocked",
                evidence=f"Ticket {ticket.ticket_id} timed out after {ticket.timeout_seconds}s."
            ))
        elif approved:
            ticket.status = "APPROVED"
            ticket.decision_notes = notes or "Approved by engineering governance"
            decision.state = ReleaseGateDecisionState.RELEASE_READY_WITH_RISK
            decision.allowed_to_release = True
        else:
            ticket.status = "REJECTED"
            ticket.decision_notes = notes or "Rejected by human reviewer"
            decision.state = ReleaseGateDecisionState.BLOCKED
            decision.allowed_to_release = False
            decision.blockers.append(ReleaseBlocker(
                blocker_id=f"blocker-hr-rejected-{ticket.ticket_id}",
                category=BlockerCategory.QUALITY_GATE_BLOCKED,
                description="Human review rejected candidate release",
                evidence=ticket.decision_notes
            ))

        # Recompute provenance
        payload = {
            "decision_id": decision.decision_id,
            "candidate_id": decision.candidate_id,
            "state": decision.state.value if hasattr(decision.state, "value") else str(decision.state),
            "ticket_status": ticket.status,
            "allowed_to_release": decision.allowed_to_release
        }
        decision.provenance_hash = ReleaseProvenanceTracker.compute_sha256(payload)
        return decision
