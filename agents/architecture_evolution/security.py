"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: security.py
Security sentinel filter validating architectural proposals against secret exposure,
privilege escalation, destructive commands, and uncontrolled side effects.

Rule:
    No architecture proposal may bypass the Security Sentinel.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from .models import ArchitectureAlternative


class ArchitectureSecurityFilter:
    """Filters out architecturally unsafe, destructive, or privileged proposals."""

    BLOCKED_PATTERNS = [
        re.compile(r"(?i)\b(api[_-]?key|secret|password|token|bearer|credential)\b.*="),
        re.compile(r"(?i)\b(drop\s+database|rm\s+-rf|del\s+/f|shred|truncate\s+table)\b"),
        re.compile(r"(?i)\b(stripe|paypal|crypto|payment|wallet)\.charge\b"),
        re.compile(r"(?i)\b(chmod\s+777|sudo|runas|setuid)\b"),
    ]

    def validate_proposal(
        self,
        alternative: ArchitectureAlternative,
        context: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        Validates the alternative and proposed changes against security sentinels.
        Returns (is_secure, violations).
        """
        violations: List[str] = []

        # 1. Inspect title, description, and benefits
        text_to_scan = f"{alternative.title} {alternative.description} {' '.join(alternative.benefits)} {' '.join(alternative.costs)}"
        for pattern in self.BLOCKED_PATTERNS:
            if pattern.search(text_to_scan):
                violations.append(f"Security violation: dangerous pattern '{pattern.pattern}' detected in proposal text.")

        # 2. Inspect affected components
        for comp in alternative.affected_components:
            for pattern in self.BLOCKED_PATTERNS:
                if pattern.search(comp):
                    violations.append(f"Security violation: affected component '{comp}' matches prohibited pattern.")

        # 3. Check for external path leakage
        for comp in alternative.affected_components:
            if ".." in comp or comp.startswith("/") or (len(comp) > 1 and comp[1] == ":"):
                # Potential path traversal outside workspace
                if "desktop" not in comp.lower() and "jarvis" not in comp.lower():
                    violations.append(f"Security boundary violation: component path '{comp}' targets external location.")

        # 4. Check context payload for raw secrets
        context_str = str(context)
        for pattern in self.BLOCKED_PATTERNS:
            if pattern.search(context_str):
                violations.append("Security violation: prohibited credential or destructive pattern in migration context.")

        is_secure = len(violations) == 0
        return is_secure, violations
