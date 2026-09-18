"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: verification.py
Generates multi-layer verification requirements integrating F61 (Autonomous Test Synthesis)
and F62 (Continuous Verification & Regression Governance).
"""

from __future__ import annotations

import hashlib
from typing import List

from .models import (
    ArchitectureAlternative,
    ArchitectureSnapshot,
    ImpactAnalysisResult,
    VerificationPlan,
)


class ArchitectureVerificationPlanner:
    """Derives comprehensive multi-axis verification plans for architectural candidates."""

    def plan_verification(
        self,
        alternative: ArchitectureAlternative,
        impact: ImpactAnalysisResult,
        snapshot: ArchitectureSnapshot,
    ) -> VerificationPlan:
        plan_id = f"verif_{hashlib.sha256(alternative.alternative_id.encode()).hexdigest()[:8]}"

        # 1. Required Tests (Unit, Integration, Downstream)
        req_tests = list(impact.affected_tests)
        for comp in alternative.affected_components:
            req_tests.append(f"tests/test_{comp.replace('/', '_').replace('.', '_')}_refactor.py")
        if not req_tests:
            req_tests.append("tests/test_full_architecture_regression.py")

        # 2. Required Contract Checks
        req_contracts = [
            f"contract_assert_{c}" for c in impact.affected_contracts
        ]
        if not req_contracts:
            req_contracts.append("verify_zero_contract_drift_in_subsystem")

        # 3. Required Behavior Checks
        req_behavior = [
            "verify_invocation_ordering_invariants",
            "verify_idempotency_under_network_partition",
            "verify_timeout_and_backoff_stability",
        ]

        # 4. Required Browser Checks
        req_browser = []
        if impact.browser_surfaces:
            req_browser.extend([
                f"playwright_spec_{b}" for b in impact.browser_surfaces
            ])
            req_browser.append("verify_browser_console_zero_errors")

        # 5. Required Migration Checks
        req_migration = [
            "verify_preflight_configuration_readiness",
            "verify_dual_execution_result_parity",
            "verify_canary_traffic_routing_metrics",
        ]

        # 6. Required Rollback Checks
        req_rollback = [
            "verify_feature_flag_immediate_deactivation",
            "verify_rollback_state_cleanliness",
        ]

        # 7. Required Security Checks
        req_security = [
            "security_sentinel_secret_leak_audit",
            "privilege_boundary_integrity_scan",
            "dependency_vulnerability_cve_check",
        ]

        return VerificationPlan(
            plan_id=plan_id,
            alternative_id=alternative.alternative_id,
            required_tests=sorted(list(set(req_tests))),
            required_contract_checks=sorted(list(set(req_contracts))),
            required_behavior_checks=req_behavior,
            required_browser_checks=sorted(list(set(req_browser))),
            required_migration_checks=req_migration,
            required_rollback_checks=req_rollback,
            required_security_checks=req_security,
        )
