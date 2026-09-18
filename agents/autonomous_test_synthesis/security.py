"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: security.py
Security Sentinel authority protecting the workspace against malicious test generation,
destructive commands, secret leakage, data exfiltration, and sandbox escapes.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .models import TestCandidate


class TestSecuritySentinel:
    """
    Ensures that synthesized tests are strictly sandboxed and safe.
    Rejects any generated code containing destructive primitives or exfiltration attempts.
    """

    PROHIBITED_PATTERNS = [
        (r"os\.system\b", "Arbitrary system command execution prohibited"),
        (r"subprocess\.(Popen|run|call)\b", "Subprocess execution without whitelist prohibited"),
        (r"shutil\.rmtree\b", "Recursive filesystem removal prohibited"),
        (r"os\.remove\b", "Direct file deletion prohibited in synthesized test code"),
        (r"open\(.*['\"].*passwd", "Attempt to access system credential files"),
        (r"open\(.*['\"].*\.env", "Attempt to read secret environment files"),
        (r"AWS_SECRET_ACCESS_KEY|PRIVATE_KEY|id_rsa", "Secret identifier tampering or exfiltration detected"),
        (r"requests\.(post|put|patch)\b", "Direct external HTTP exfiltration prohibited in unit tests"),
        (r"urllib\.request", "Arbitrary socket or network call prohibited"),
        (r"socket\.socket\b", "Direct raw network socket forbidden in test execution"),
        (r"eval\(|exec\(", "Dynamic code evaluation (eval/exec) strictly forbidden"),
        (r"__import__\(['\"]os['\"]\)", "Obfuscated import of OS library prohibited"),
    ]

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self.workspace_root = workspace_root or ""
        self.blocked_violations: List[Dict[str, Any]] = []

    def validate_candidate_safety(self, candidate: TestCandidate) -> Tuple[bool, Optional[str]]:
        code = candidate.code

        # 1. Regex inspection of prohibited patterns
        for pattern, reason in self.PROHIBITED_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                violation = {
                    "test_id": candidate.test_id,
                    "target": candidate.target,
                    "pattern": pattern,
                    "reason": reason,
                    "code_snippet": code[:120],
                }
                self.blocked_violations.append(violation)
                return False, f"SECURITY_BLOCKED: {reason}"

        # 2. Path Traversal in files or inputs
        for f in candidate.files:
            if ".." in f or f.startswith("/") or (len(f) > 1 and f[1] == ":"):
                return False, "SECURITY_BLOCKED: Path traversal or absolute outside path in target files"

        for k, v in candidate.inputs.items():
            if isinstance(v, str) and ("../" in v or "..\\" in v):
                # Allowed only if expected_outputs marks an exception (negative testing)
                if "exception" not in candidate.expected_outputs:
                    return False, f"SECURITY_BLOCKED: Path traversal in input parameter '{k}'"

        return True, None

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return list(self.blocked_violations)
