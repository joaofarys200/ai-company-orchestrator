"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: policy.py
Verification Policy Engine defining operational profiles, resource caps, and safety constraints.
"""

from __future__ import annotations

from typing import Dict, Optional
from .models import VerificationPolicy, VerificationPolicyName


class VerificationPolicyEngine:
    """
    Manages and configures Verification Policies:
    - LOCAL: Fast feedback during interactive development, low runtime, no browser tests.
    - STANDARD: Balanced verification covering direct impact and direct consumers.
    - STRICT: Thorough verification with counterexample minimization and flaky retries.
    - CRITICAL: Maximum rigor, zero tolerance for regressions, full mutation and contract check.
    - ECONOMIC: Strictly synthetic, minimal tests, no network or heavy browser instances.
    - SECURITY: Focused on security constraints, taint boundaries, and external surface gates.
    """

    DEFAULT_POLICIES: Dict[VerificationPolicyName, VerificationPolicy] = {
        VerificationPolicyName.LOCAL: VerificationPolicy(
            name=VerificationPolicyName.LOCAL,
            max_tests=15,
            max_runtime=10.0,
            max_synthesis_attempts=1,
            max_mutation_scope=2,
            max_browser_tests=0,
            max_retries=1,
            max_memory_mb=512,
            allow_synthesis=True,
            allow_retries=True,
            fail_on_flaky=False,
            enforce_sentinel=True,
        ),
        VerificationPolicyName.STANDARD: VerificationPolicy(
            name=VerificationPolicyName.STANDARD,
            max_tests=50,
            max_runtime=60.0,
            max_synthesis_attempts=3,
            max_mutation_scope=10,
            max_browser_tests=3,
            max_retries=2,
            max_memory_mb=1024,
            allow_synthesis=True,
            allow_retries=True,
            fail_on_flaky=False,
            enforce_sentinel=True,
        ),
        VerificationPolicyName.STRICT: VerificationPolicy(
            name=VerificationPolicyName.STRICT,
            max_tests=150,
            max_runtime=180.0,
            max_synthesis_attempts=5,
            max_mutation_scope=25,
            max_browser_tests=8,
            max_retries=3,
            max_memory_mb=2048,
            allow_synthesis=True,
            allow_retries=True,
            fail_on_flaky=True,
            enforce_sentinel=True,
        ),
        VerificationPolicyName.CRITICAL: VerificationPolicy(
            name=VerificationPolicyName.CRITICAL,
            max_tests=500,
            max_runtime=600.0,
            max_synthesis_attempts=10,
            max_mutation_scope=50,
            max_browser_tests=15,
            max_retries=5,
            max_memory_mb=4096,
            allow_synthesis=True,
            allow_retries=True,
            fail_on_flaky=True,
            enforce_sentinel=True,
        ),
        VerificationPolicyName.ECONOMIC: VerificationPolicy(
            name=VerificationPolicyName.ECONOMIC,
            max_tests=10,
            max_runtime=5.0,
            max_synthesis_attempts=1,
            max_mutation_scope=0,
            max_browser_tests=0,
            max_retries=0,
            max_memory_mb=256,
            allow_synthesis=False,
            allow_retries=False,
            fail_on_flaky=False,
            enforce_sentinel=True,
        ),
        VerificationPolicyName.SECURITY: VerificationPolicy(
            name=VerificationPolicyName.SECURITY,
            max_tests=80,
            max_runtime=90.0,
            max_synthesis_attempts=4,
            max_mutation_scope=15,
            max_browser_tests=2,
            max_retries=2,
            max_memory_mb=1024,
            allow_synthesis=True,
            allow_retries=True,
            fail_on_flaky=True,
            enforce_sentinel=True,
        ),
    }

    @classmethod
    def get_policy(cls, name_or_policy: Optional[VerificationPolicyName | str | VerificationPolicy] = None) -> VerificationPolicy:
        if isinstance(name_or_policy, VerificationPolicy):
            return name_or_policy
        
        if name_or_policy is None:
            return cls.DEFAULT_POLICIES[VerificationPolicyName.STANDARD]
        
        try:
            if isinstance(name_or_policy, str):
                name_enum = VerificationPolicyName(name_or_policy.upper())
            else:
                name_enum = name_or_policy
            return cls.DEFAULT_POLICIES.get(name_enum, cls.DEFAULT_POLICIES[VerificationPolicyName.STANDARD])
        except Exception:
            return cls.DEFAULT_POLICIES[VerificationPolicyName.STANDARD]
