"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: policy.py
Policy manager governing strictness, rollback triggers, and verification requirements
across STRICT, STANDARD, DEVELOPMENT, and EMERGENCY_ROLLBACK operating modes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .models import ModificationPolicyType


class ModificationPolicyManager:
    """Configures policy parameters and guard thresholds."""

    POLICIES = {
        ModificationPolicyType.STRICT: {
            "allow_dirty": False,
            "require_full_test_suite": True,
            "require_behavior_proof": True,
            "require_browser_qa": True,
            "require_clean_rescan": True,
            "max_iterations": 3,
            "max_wall_time_sec": 180.0,
            "strict_sentinel": True,
        },
        ModificationPolicyType.STANDARD: {
            "allow_dirty": False,
            "require_full_test_suite": False,  # Run impacted tests + regressions
            "require_behavior_proof": True,
            "require_browser_qa": False,
            "require_clean_rescan": True,
            "max_iterations": 5,
            "max_wall_time_sec": 300.0,
            "strict_sentinel": True,
        },
        ModificationPolicyType.DEVELOPMENT: {
            "allow_dirty": True,  # Explicit policy override for dev workspace
            "require_full_test_suite": False,
            "require_behavior_proof": False,
            "require_browser_qa": False,
            "require_clean_rescan": False,
            "max_iterations": 10,
            "max_wall_time_sec": 600.0,
            "strict_sentinel": True,
        },
        ModificationPolicyType.EMERGENCY_ROLLBACK: {
            "allow_dirty": True,
            "require_full_test_suite": False,
            "require_behavior_proof": False,
            "require_browser_qa": False,
            "require_clean_rescan": False,
            "max_iterations": 1,
            "max_wall_time_sec": 60.0,
            "strict_sentinel": True,
        },
    }

    def get_policy_config(self, policy_type: ModificationPolicyType = ModificationPolicyType.STANDARD) -> Dict[str, Any]:
        return dict(self.POLICIES.get(policy_type, self.POLICIES[ModificationPolicyType.STANDARD]))
