"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: security.py
Security Sentinel enforcing absolute boundary protection against destructive actions,
credential leakage, and unauthorized modifications to critical governance/sentinel code.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


class SecuritySentinel:
    """Supreme authority evaluating self-modification safety."""

    PROTECTED_SYSTEM_PATHS = {
        "backend/agents/safe_self_modification/governance.py",
        "backend/agents/safe_self_modification/security.py",
        "backend/agents/safe_self_modification/rollback.py",
        "backend/agents/safe_self_modification/provenance.py",
        "agents/safe_self_modification/governance.py",
        "agents/safe_self_modification/security.py",
        "agents/safe_self_modification/rollback.py",
        "agents/safe_self_modification/provenance.py",
    }

    DESTRUCTIVE_PATTERNS = [
        (r"shutil\.rmtree\s*\(", "DESTRUCTIVE_FILESYSTEM: shutil.rmtree call detected."),
        (r"os\.system\s*\(", "UNCONTROLLED_EXECUTION: os.system call detected."),
        (r"subprocess\.run\(.*rm\s+-rf", "DESTRUCTIVE_COMMAND: rm -rf command detected."),
        (r"format\s+[A-Za-z]:", "DESTRUCTIVE_DRIVE_OPERATION: Drive format command detected."),
        (r"(?i)api[_-]?key\s*=\s*['\"][a-zA-Z0-9_\-]{16,}['\"]", "SECRET_LEAKAGE: Raw API key hardcoded."),
        (r"(?i)password\s*=\s*['\"][^'\"]{6,}['\"]", "SECRET_LEAKAGE: Password literal hardcoded."),
        (r"(?i)private[_-]?key\s*=\s*['\"][^'\"]+['\"]", "CREDENTIAL_EXPOSURE: Private key literal detected."),
        (r"(?i)stripe\.Charge\.create", "FINANCIAL_MUTATION: Real payment API call detected."),
        (r"(?i)wallet\.transfer", "FINANCIAL_MUTATION: Cryptocurrency wallet transfer detected."),
    ]

    def check_file_path_safety(
        self,
        file_path: str,
        explicit_human_approval: bool = False,
    ) -> Tuple[bool, str]:
        """Check if target file belongs to protected governance or sentinel paths."""
        normalized = file_path.replace("\\", "/").strip()

        for prot in self.PROTECTED_SYSTEM_PATHS:
            if prot in normalized:
                if not explicit_human_approval:
                    return (
                        False,
                        f"PROTECTED_PATH_BLOCKED: '{file_path}' cannot be self-modified without EXPLICIT_HUMAN_APPROVAL.",
                    )

        return True, "PATH_SAFE: Path is within allowable self-modification boundary."

    def scan_content_safety(self, diff_or_content: str) -> Tuple[bool, List[str]]:
        """Scan content or patch diff for destructive commands, secrets, or financial calls."""
        violations: List[str] = []

        for pattern, msg in self.DESTRUCTIVE_PATTERNS:
            if re.search(pattern, diff_or_content):
                violations.append(msg)

        if violations:
            return False, violations

        return True, ["SECURITY_SCAN_PASSED: Zero destructive patterns or secret exposures observed."]
