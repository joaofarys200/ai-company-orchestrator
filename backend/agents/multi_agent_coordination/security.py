"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: security.py
SecuritySentinel exercising supreme non-overridable authority over multi-agent operations.
Priority scores cannot bypass security policies. No agent may delegate permissions to another.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


class SecuritySentinel:
    """Supreme coordination security boundary enforcing protected paths and command safety."""

    PROTECTED_SYSTEM_PATHS = {
        "governance.py",
        "security.py",
        "rollback.py",
        "provenance.py",
        ".env",
        "secrets",
        "credentials",
        "id_rsa",
        ".pem",
    }

    DESTRUCTIVE_PATTERNS = [
        (r"shutil\.rmtree\s*\(", "DESTRUCTIVE_FILESYSTEM: shutil.rmtree call detected."),
        (r"os\.system\s*\(", "UNCONTROLLED_EXECUTION: os.system call detected."),
        (r"subprocess\.run\(.*rm\s+-rf", "DESTRUCTIVE_COMMAND: rm -rf command detected."),
        (r"(?i)api[_-]?key\s*=\s*['\"][a-zA-Z0-9_\-]{16,}['\"]", "SECRET_LEAKAGE: Raw API key hardcoded."),
        (r"(?i)password\s*=\s*['\"][^'\"]{6,}['\"]", "SECRET_LEAKAGE: Password literal hardcoded."),
        (r"(?i)stripe\.Charge\.create", "FINANCIAL_MUTATION: Payment API invocation detected."),
    ]

    def validate_file_safety(self, file_path: str) -> Tuple[bool, str]:
        """Verify that target file path does not violate protected sentinel boundaries."""
        norm = file_path.replace("\\", "/").strip()
        for prot in self.PROTECTED_SYSTEM_PATHS:
            if prot in norm:
                return False, f"SECURITY_BLOCK: '{file_path}' is protected and cannot be modified by multi-agent coordination."
        return True, "PATH_SAFE: Path is within allowable coordination bounds."

    def validate_content_safety(self, diff_or_content: str) -> Tuple[bool, List[str]]:
        """Scan patch diff for destructive commands, secret credentials, or financial operations."""
        violations: List[str] = []
        for pattern, desc in self.DESTRUCTIVE_PATTERNS:
            if re.search(pattern, diff_or_content):
                violations.append(desc)
        return len(violations) == 0, violations

    def validate_delegation_attempt(self, delegator_agent: str, target_agent: str) -> Tuple[bool, str]:
        """Strictly prohibit agents from granting security permissions or bypassing gates for peers."""
        return False, f"PERMISSION_DELEGATION_PROHIBITED: Agent '{delegator_agent}' cannot grant permissions to '{target_agent}'."
