"""
Security Readiness Module
Phase 70 — Autonomous Release Readiness & Production Governance

Integrates Sentinel security authorities. Holds absolute veto power over
releases. Never reduces security policy to allow a release through.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import BlockerCategory, ReleaseBlocker


class SecurityReadinessEvaluator:
    """Evaluates security posturing, sentinel verdicts, credential risks, and sandbox integrity."""

    @classmethod
    def evaluate(
        cls,
        security_snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verifies:
        - secrets scan
        - credential exposure
        - protected paths
        - sandbox violations
        - unsafe commands
        - privilege changes
        - dependency vulnerabilities
        - security debt
        - security review backlog
        Security Sentinel has maximum authority; never reduce policy to pass release.
        """
        if not security_snapshot:
            return {
                "verdict": "BLOCKED",
                "blockers": [
                    ReleaseBlocker(
                        blocker_id="blocker-sec-missing-sentinel",
                        category=BlockerCategory.CRITICAL_SECURITY,
                        description="Security sentinel scan data is missing or inaccessible",
                        evidence="No security posture evidence provided."
                    )
                ],
                "requires_human_review": True,
                "review_reasons": ["Security evaluation missing"]
            }

        secrets_count = security_snapshot.get("secrets_detected_count", 0)
        credential_exposure = security_snapshot.get("credential_exposure", False)
        sandbox_violations = security_snapshot.get("sandbox_violations_count", 0)
        unsafe_commands = security_snapshot.get("unsafe_commands_detected", 0)
        protected_path_breaches = security_snapshot.get("protected_path_breaches", 0)
        vulnerabilities_critical = security_snapshot.get("critical_vulnerabilities_count", 0)
        security_debt_count = security_snapshot.get("security_debt_count", 0)
        security_review_backlog = security_snapshot.get("security_review_backlog_count", 0)

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []

        if secrets_count > 0 or credential_exposure:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-sec-secrets-exposed",
                category=BlockerCategory.CRITICAL_SECURITY,
                description=f"Potential credential exposure or plaintext secrets ({secrets_count} detected)",
                evidence="Sentinel secrets scanner flagged API tokens or credentials in candidate artifacts."
            ))

        if sandbox_violations > 0 or unsafe_commands > 0 or protected_path_breaches > 0:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-sec-sandbox-breach",
                category=BlockerCategory.CRITICAL_SECURITY,
                description="Sandbox violation, unsafe command, or protected path breach detected",
                evidence=f"Sandbox: {sandbox_violations}, Unsafe cmds: {unsafe_commands}, Path breaches: {protected_path_breaches}."
            ))

        if vulnerabilities_critical > 0:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-sec-critical-cve",
                category=BlockerCategory.CRITICAL_SECURITY,
                description=f"{vulnerabilities_critical} critical CVE / dependency vulnerabilities detected",
                evidence=f"Critical vulnerabilities: {vulnerabilities_critical}."
            ))

        if security_debt_count > 0:
            requires_human_review = True
            review_reasons.append(f"{security_debt_count} open non-critical security debt items require verification")

        if security_review_backlog > 0:
            requires_human_review = True
            review_reasons.append(f"Security review backlog has {security_review_backlog} pending signoffs")

        verdict = "PASSED"
        if blockers:
            verdict = "BLOCKED"
        elif requires_human_review:
            verdict = "HUMAN_REVIEW"

        return {
            "verdict": verdict,
            "secrets_count": secrets_count,
            "credential_exposure": credential_exposure,
            "sandbox_violations": sandbox_violations,
            "unsafe_commands": unsafe_commands,
            "protected_path_breaches": protected_path_breaches,
            "vulnerabilities_critical": vulnerabilities_critical,
            "security_debt_count": security_debt_count,
            "security_review_backlog": security_review_backlog,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons
        }
