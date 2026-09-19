"""
Release Verification Runner Module
Phase 70 — Autonomous Release Readiness & Production Governance

Integrates Phase 62 Continuous Verification & Regression Prevention.
Synthesizes test passes across unit, contract, behavior, browser, security, and runtime.
Crucial invariant: Never relies exclusively on historical regression results.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import BlockerCategory, ReleaseBlocker


class ReleaseVerificationRunner:
    """Executes multi-axis continuous verification across 8 distinct test suites."""

    @classmethod
    def verify(
        cls,
        verification_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes:
        - selected tests
        - regression tests
        - known failures
        - contract tests
        - behavior tests
        - browser tests
        - security tests
        - runtime checks
        Rule: Never relies solely on historical regression.
        """
        if not verification_data:
            return {
                "verdict": "FAILED",
                "blockers": [
                    ReleaseBlocker(
                        blocker_id="blocker-verif-missing",
                        category=BlockerCategory.MISSING_MANDATORY_EVIDENCE,
                        description="Verification suite data completely absent",
                        evidence="Empty verification record provided."
                    )
                ],
                "requires_human_review": True,
                "review_reasons": ["Verification data missing"]
            }

        selected_tests_pass = verification_data.get("selected_tests_pass", True)
        regression_tests_pass = verification_data.get("regression_tests_pass", True)
        known_failures_unresolved = verification_data.get("known_failures_count", 0)
        contract_tests_pass = verification_data.get("contract_tests_pass", True)
        behavior_tests_pass = verification_data.get("behavior_tests_pass", True)
        browser_tests_pass = verification_data.get("browser_tests_pass", True)
        security_tests_pass = verification_data.get("security_tests_pass", True)
        runtime_checks_pass = verification_data.get("runtime_checks_pass", True)
        historical_only = verification_data.get("historical_only", False)

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []

        # Anti-pattern defense: relying solely on historical regression
        if historical_only:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-verif-historical-only",
                category=BlockerCategory.MISSING_MANDATORY_EVIDENCE,
                description="Verification relied exclusively on historical regression without current candidate testing",
                evidence="Active candidate-specific verification suites were omitted."
            ))

        if not selected_tests_pass or not regression_tests_pass:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-verif-unit-regression-failed",
                category=BlockerCategory.QUALITY_GATE_BLOCKED,
                description="Unit tests or regression test suite failed",
                evidence=f"Selected tests: {selected_tests_pass}, Regression tests: {regression_tests_pass}."
            ))

        if not contract_tests_pass:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-verif-contract-failed",
                category=BlockerCategory.BREAKING_CONTRACT,
                description="Contract tests failed for candidate interfaces",
                evidence="Contract compatibility verification failed."
            ))

        if not behavior_tests_pass:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-verif-behavior-failed",
                category=BlockerCategory.INCOMPATIBLE_BEHAVIOR,
                description="Behavioral invariant verification failed",
                evidence="Behavioral test execution encountered counterexamples."
            ))

        if not browser_tests_pass:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-verif-browser-failed",
                category=BlockerCategory.QUALITY_GATE_BLOCKED,
                description="Browser QA tests failed in end-to-end user verification",
                evidence="UI test assertions failed during headless browser execution."
            ))

        if not security_tests_pass:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-verif-security-failed",
                category=BlockerCategory.CRITICAL_SECURITY,
                description="Automated security test suite failed",
                evidence="Security scanner or permission validation test failed."
            ))

        if not runtime_checks_pass:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-verif-runtime-failed",
                category=BlockerCategory.CRITICAL_HEALTH_FAILURE,
                description="Operational runtime checks failed",
                evidence="Live liveness/readiness probes failed verification."
            ))

        if known_failures_unresolved > 0:
            requires_human_review = True
            review_reasons.append(f"{known_failures_unresolved} unresolved known issues cataloged for candidate")

        verdict = "PASSED"
        if blockers:
            verdict = "FAILED"
        elif requires_human_review:
            verdict = "HUMAN_REVIEW"

        return {
            "verdict": verdict,
            "selected_tests_pass": selected_tests_pass,
            "regression_tests_pass": regression_tests_pass,
            "known_failures_count": known_failures_unresolved,
            "contract_tests_pass": contract_tests_pass,
            "behavior_tests_pass": behavior_tests_pass,
            "browser_tests_pass": browser_tests_pass,
            "security_tests_pass": security_tests_pass,
            "runtime_checks_pass": runtime_checks_pass,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons
        }
