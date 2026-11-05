"""
JARVIS OS — Phase 77: Autonomous Evidence Verification & Engineering Claims Governance
Module: report_auditor.py
Audits engineering completion reports against ground-truth evidence, exposing unverified claims,
contradictions, and synthetic benchmarks.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    EngineeringClaim,
    ReportAuditResult,
    VerificationStatus,
)
from .registry import EvidenceClaimsRegistry


class CompletionReportAuditor:
    """
    Audits Phase completion reports (e.g. docs/PHASE_*_REPORT.md) to ensure every asserted claim
    is backed by verified authoritative evidence, preventing fabricated success reports.
    """

    def __init__(self, registry: EvidenceClaimsRegistry):
        self.registry = registry

    def audit_report_claims(
        self,
        report_path: str,
        associated_claims: List[EngineeringClaim],
    ) -> ReportAuditResult:
        """
        Audits a list of claims representing the statements in a completion report.
        """
        verified = [c for c in associated_claims if c.status == VerificationStatus.VERIFIED]
        unverified = [c for c in associated_claims if c.status in (
            VerificationStatus.UNVERIFIED, VerificationStatus.PARTIALLY_VERIFIED
        )]
        contradicted = [c for c in associated_claims if c.status == VerificationStatus.CONTRADICTED]
        stale = [c for c in associated_claims if c.status == VerificationStatus.STALE]

        rejections: List[str] = []
        if contradicted:
            rejections.append(f"Report contains {len(contradicted)} CONTRADICTED claim(s): {[c.claim_id for c in contradicted]}")
        if stale:
            rejections.append(f"Report contains {len(stale)} STALE claim(s): {[c.claim_id for c in stale]}")
        if unverified:
            rejections.append(f"Report contains {len(unverified)} UNVERIFIED claim(s): {[c.claim_id for c in unverified]}")

        is_acceptable = len(contradicted) == 0 and len(stale) == 0 and len(unverified) == 0

        claim_details = [
            {
                "claim_id": c.claim_id,
                "type": c.claim_type.value,
                "proposition": c.proposition,
                "status": c.status.value,
                "tier": c.assurance_tier.value,
                "explanation": c.verification_result.explanation if c.verification_result else "Unexamined",
            }
            for c in associated_claims
        ]

        return ReportAuditResult(
            report_path=report_path,
            total_claims=len(associated_claims),
            verified_count=len(verified),
            unverified_count=len(unverified),
            contradicted_count=len(contradicted),
            stale_count=len(stale),
            claims_details=claim_details,
            is_acceptable=is_acceptable,
            rejection_reasons=rejections,
        )

    def extract_text_claims(self, markdown_text: str) -> List[Dict[str, str]]:
        """
        Heuristic extraction of key factual assertions from completion report markdown.
        """
        extracted = []
        # Check Status line
        m_status = re.search(r"\*\*Status\*\*:\s*`?([A-Z_]+)`?", markdown_text)
        if m_status:
            extracted.append({"type": "STATUS_CLAIM", "text": f"Report declares status: {m_status.group(1)}"})

        # Check Test pass counts
        m_tests = re.search(r"(\d+)\s+passed", markdown_text)
        if m_tests:
            extracted.append({"type": "TEST_COUNT_CLAIM", "text": f"Report claims {m_tests.group(1)} passed tests"})

        # Check Zero failures
        if "0 failed" in markdown_text or "zero failures" in markdown_text.lower():
            extracted.append({"type": "ZERO_FAILURES_CLAIM", "text": "Report claims zero test failures"})

        return extracted
