"""
JARVIS OS — Phase 77: Autonomous Evidence Verification & Engineering Claims Governance
Module: bridge.py
Master orchestrator implementing the 9-stage closed-loop evidence verification lifecycle.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .adapters import (
    Phase73MacroRefactoringAdapter,
    Phase74ArchitecturalOptimizationAdapter,
    Phase75PortfolioOrchestrationAdapter,
    Phase76PredictiveCalibrationAdapter,
)
from .contradiction import ContradictionDetector
from .enforcement import GovernanceEnforcementEngine
from .freshness import EvidenceFreshnessMonitor
from .models import (
    AssuranceTier,
    ClaimType,
    EngineeringClaim,
    EvidenceArtifact,
    EvidenceCategory,
    EvidenceOriginType,
    ReportAuditResult,
    VerificationResult,
    VerificationStatus,
)
from .persistence import EvidenceGovernanceStore
from .provenance import EvidenceProvenanceValidator
from .registry import EvidenceClaimsRegistry
from .report_auditor import CompletionReportAuditor
from .verifier import ClaimToEvidenceVerifier


class EvidenceGovernanceBridge:
    """
    Central strategic bridge for Phase 77.
    Coordinates claim registration, evidence ingestion, deterministic verification,
    freshness invalidation, contradiction reconciliation, and report auditing.
    """

    def __init__(self, store_dir: str = ".jarvis/evidence_governance"):
        self.store = EvidenceGovernanceStore(base_dir=store_dir)
        self.registry = EvidenceClaimsRegistry()
        self.verifier = ClaimToEvidenceVerifier()
        self.freshness = EvidenceFreshnessMonitor()
        self.contradiction = ContradictionDetector()
        self.enforcement = GovernanceEnforcementEngine()
        self.report_auditor = CompletionReportAuditor(self.registry)

        # Recover persisted state
        self.store.reconcile_and_recover(self.registry)

        # Subsystem adapters
        self.phase73_adapter = Phase73MacroRefactoringAdapter(self.registry)
        self.phase74_adapter = Phase74ArchitecturalOptimizationAdapter(self.registry)
        self.phase75_adapter = Phase75PortfolioOrchestrationAdapter(self.registry)
        self.phase76_adapter = Phase76PredictiveCalibrationAdapter(self.registry)

    def assert_claim(
        self,
        claim_id: str,
        claim_type: ClaimType,
        proposition: str,
        assurance_tier: AssuranceTier,
        originating_subsystem: str,
        required_evidence_categories: List[EvidenceCategory],
        dependency_files: Optional[List[str]] = None,
        commit_sha: Optional[str] = None,
    ) -> EngineeringClaim:
        """Stage 1, 2, 3: Formulate, classify, and register a typed engineering claim."""
        claim = EngineeringClaim(
            claim_id=claim_id,
            claim_type=claim_type,
            proposition=proposition,
            assurance_tier=assurance_tier,
            originating_subsystem=originating_subsystem,
            required_evidence_categories=required_evidence_categories,
            dependency_files=dependency_files or [],
            commit_sha=commit_sha,
            created_at=time.time(),
        )
        self.registry.register_claim(claim)
        self.store.save_claim(claim)
        return claim

    def ingest_evidence(
        self,
        artifact_id: str,
        category: EvidenceCategory,
        origin_type: EvidenceOriginType,
        commit_sha: str,
        payload: Dict,
        source_subsystem: str,
        claim_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> EvidenceArtifact:
        """Stage 4 & 5: Collect and validate provenance of an evidence artifact."""
        artifact = EvidenceProvenanceValidator.create_artifact(
            artifact_id=artifact_id,
            category=category,
            origin_type=origin_type,
            commit_sha=commit_sha,
            payload=payload,
            source_subsystem=source_subsystem,
            metadata=metadata,
        )
        registered = self.registry.register_artifact(artifact)
        self.store.save_artifact(registered)

        if claim_id:
            self.registry.attach_evidence_to_claim(claim_id, registered.artifact_id)
            claim = self.registry.get_claim(claim_id)
            if claim:
                self.store.save_claim(claim)

        return registered

    def verify_claim(self, claim_id: str) -> VerificationResult:
        """Stage 6 & 7: Evaluate claim against attached evidence artifacts."""
        claim = self.registry.get_claim(claim_id)
        if not claim:
            return VerificationResult(
                status=VerificationStatus.UNVERIFIED,
                explanation=f"Claim '{claim_id}' not found in registry.",
            )

        artifacts = self.registry.get_artifacts_for_claim(claim)

        # Check for contradictions first if multiple evidence artifacts exist
        if len(artifacts) >= 2:
            status, contra_record = self.contradiction.detect_and_reconcile_contradictions(claim, artifacts)
            if status in (VerificationStatus.CONTRADICTED, VerificationStatus.INCONCLUSIVE):
                res = VerificationResult(
                    status=status,
                    explanation=contra_record.description if contra_record else "Contradiction detected.",
                    supporting_evidence_ids=[a.artifact_id for a in artifacts],
                    discrepancies=[f"CONTRADICTION_{status.value}"],
                )
                claim.status = status
                claim.verification_result = res
                self.store.save_claim(claim)
                return res

        # Run deterministic category verification
        res = self.verifier.verify_claim(claim, artifacts)
        self.store.save_claim(claim)

        # Record in audit ledger
        self.store.record_audit_entry({
            "action": "VERIFY_CLAIM",
            "claim_id": claim.claim_id,
            "status": res.status.value,
            "tier": claim.assurance_tier.value,
            "timestamp": time.time(),
        })
        return res

    def invalidate_by_files(self, modified_files: Set[str]) -> List[str]:
        """Detect stale claims when dependency files are modified."""
        all_claims = self.registry.list_claims()
        invalidated_ids = self.freshness.evaluate_freshness_against_modified_files(all_claims, modified_files)
        for c_id in invalidated_ids:
            claim = self.registry.get_claim(c_id)
            if claim:
                self.store.save_claim(claim)
                self.store.record_audit_entry({
                    "action": "INVALIDATE_CLAIM_STALE",
                    "claim_id": c_id,
                    "modified_files": list(modified_files),
                    "timestamp": time.time(),
                })
        return invalidated_ids

    def audit_report(
        self,
        report_path: str,
        associated_claims: List[EngineeringClaim],
    ) -> ReportAuditResult:
        """Stage 8: Audit a completion report against ground-truth claims."""
        return self.report_auditor.audit_report_claims(report_path, associated_claims)

    def enforce_promotion(self, claim_id: str) -> None:
        """Stage 8: Enforce governance gate for claim promotion."""
        claim = self.registry.get_claim(claim_id)
        if not claim:
            raise KeyError(f"Claim '{claim_id}' not found.")
        self.enforcement.enforce_promotion(claim)
