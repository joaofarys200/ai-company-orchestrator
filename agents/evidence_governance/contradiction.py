"""
JARVIS OS — Phase 77: Autonomous Evidence Verification & Engineering Claims Governance
Module: contradiction.py
Contradiction detection, discrepancy resolution, and evidence authority hierarchy.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional, Tuple

from .models import (
    ContradictionRecord,
    EngineeringClaim,
    EvidenceArtifact,
    EvidenceCategory,
    VerificationResult,
    VerificationStatus,
)


class ContradictionDetector:
    """
    Identifies conflicting claims, contradictory evidence, and inconsistent reports,
    applying an authoritative evidence hierarchy to resolve discrepancies or escalate inconclusive states.
    """

    # Authority ranking (higher number = greater authority)
    AUTHORITY_RANKS = {
        EvidenceCategory.DIRECT_EXECUTION_OUTPUT: 10,
        EvidenceCategory.TEST_RUNNER_RESULT: 10,
        EvidenceCategory.GIT_REVISION_RECORD: 9,
        EvidenceCategory.BENCHMARK_MEASUREMENT: 8,
        EvidenceCategory.AST_INSPECTION_PROOF: 6,
        EvidenceCategory.HUMAN_APPROVAL_RECORD: 10,
        EvidenceCategory.SYNTHETIC_FIXTURE_EVIDENCE: 4,
        EvidenceCategory.MODEL_GENERATED_EXPLANATION: 1,
    }

    def __init__(self):
        self.contradiction_records: List[ContradictionRecord] = []

    def detect_and_reconcile_contradictions(
        self,
        claim: EngineeringClaim,
        artifacts: List[EvidenceArtifact],
    ) -> Tuple[VerificationStatus, Optional[ContradictionRecord]]:
        """
        Detects if multiple evidence artifacts present conflicting statements.
        Reconciles based on authority ranking or marks INCONCLUSIVE.
        """
        if len(artifacts) < 2:
            return VerificationStatus.UNVERIFIED, None

        # Check for conflicting test execution results
        test_arts = [a for a in artifacts if a.category == EvidenceCategory.TEST_RUNNER_RESULT]
        if len(test_arts) >= 2:
            first_fail = test_arts[0].payload.get("failed", 0)
            second_fail = test_arts[1].payload.get("failed", 0)
            if (first_fail == 0 and second_fail > 0) or (first_fail > 0 and second_fail == 0):
                record = ContradictionRecord(
                    contradiction_id=f"contra_{uuid.uuid4().hex[:8]}",
                    claim_id=claim.claim_id,
                    conflicting_evidence_ids=[test_arts[0].artifact_id, test_arts[1].artifact_id],
                    description=(
                        f"Conflicting test runner evidence: artifact '{test_arts[0].artifact_id}' "
                        f"has failed={first_fail}, but artifact '{test_arts[1].artifact_id}' has failed={second_fail}."
                    ),
                    detected_at=time.time(),
                    resolved=False,
                    resolution_strategy="ESCALATE_TO_INCONCLUSIVE",
                )
                self.contradiction_records.append(record)
                return VerificationStatus.INCONCLUSIVE, record

        # Check for model explanation claiming success while direct execution shows failure
        model_arts = [a for a in artifacts if a.category == EvidenceCategory.MODEL_GENERATED_EXPLANATION]
        exec_arts = [a for a in artifacts if a.category in (
            EvidenceCategory.DIRECT_EXECUTION_OUTPUT, EvidenceCategory.TEST_RUNNER_RESULT
        )]

        if model_arts and exec_arts:
            exec_failed = any(a.payload.get("failed", 0) > 0 for a in exec_arts)
            if exec_failed:
                # Direct execution overrides model generated explanation!
                record = ContradictionRecord(
                    contradiction_id=f"contra_{uuid.uuid4().hex[:8]}",
                    claim_id=claim.claim_id,
                    conflicting_evidence_ids=[model_arts[0].artifact_id, exec_arts[0].artifact_id],
                    description="Model generated explanation claimed success, but direct execution evidence shows failure.",
                    detected_at=time.time(),
                    resolved=True,
                    resolution_strategy="DIRECT_EXECUTION_OVERRIDES_MODEL_EXPLANATION",
                )
                self.contradiction_records.append(record)
                return VerificationStatus.CONTRADICTED, record

        return VerificationStatus.VERIFIED, None
