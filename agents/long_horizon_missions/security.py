"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Security Sentinel & Safe Self-Modification Gate (Integrating F65).
Enforces that missions cannot write directly to the workspace without transactional governance.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple


class SecurityViolationError(Exception):
    """Raised when an untrusted or unsafe mutation is attempted."""
    pass


class MissionSecuritySentinel:
    """
    Enforces security isolation:
    - No direct unmanaged workspace writes
    - Path traversal prevention
    - Secret and token leak prevention
    - Safe self-modification transactions (F65)
    """

    FORBIDDEN_PATTERNS = [
        r"__import__\s*\(\s*['\"]os['\"]\s*\)\s*\.system",
        r"subprocess\.Popen\s*\(.*shell\s*=\s*True",
        r"os\.system\s*\(",
        r"cat\s+\.env",
        r"rm\s+-rf\s+/",
        r"eval\s*\(",
        r"exec\s*\(",
        r"\.\./\.\./",
    ]

    FORBIDDEN_TARGET_FILES = [
        ".env",
        ".git/",
        "id_rsa",
        "id_ed25519",
        "passwd",
        "shadow",
    ]

    def __init__(self, policy: str = "SANDBOXED_F65"):
        self.policy = policy
        self.audit_log: List[Dict[str, Any]] = []

    def validate_mutation_intent(
        self,
        agent_id: str,
        target_files: List[str],
        patch_content: str,
    ) -> Tuple[bool, List[str]]:
        violations: List[str] = []

        # 1. Target file checks
        for f in target_files:
            for forbidden in self.FORBIDDEN_TARGET_FILES:
                if forbidden in f:
                    violations.append(f"FORBIDDEN_TARGET_FILE: {f}")

        # 2. Path traversal
        for f in target_files:
            if ".." in f or f.startswith("/") or (len(f) > 1 and f[1] == ":"):
                violations.append(f"UNSAFE_PATH_TRAVERSAL: {f}")

        # 3. Malicious pattern checks
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, patch_content):
                violations.append(f"MALICIOUS_PATTERN_DETECTED: {pattern}")

        is_safe = len(violations) == 0
        self.audit_log.append({
            "timestamp": time.time(),
            "agent_id": agent_id,
            "target_files": target_files,
            "is_safe": is_safe,
            "violations": violations,
        })
        return is_safe, violations
