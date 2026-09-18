"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: security.py
Security Sentinel authority guarding continuous verification cycles against destructive actions,
credential exfiltration, real payments, and uncontained sandbox escapes.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


class VerificationSecuritySentinel:
    """
    Security Sentinel for Continuous Verification.
    Validates changes, test code, execution plans, and runtime missions.
    Continuous Verification NEVER bypasses this sentinel.
    """
    __test__ = False  # Prevent pytest collection warning

    PROHIBITED_PATTERNS = [
        (r"os\.system\b", "Arbitrary system command execution prohibited"),
        (r"subprocess\.(Popen|run|call)\b", "Subprocess execution without whitelist prohibited"),
        (r"(shutil\.)?rmtree\b", "Recursive filesystem removal prohibited"),
        (r"os\.(remove|unlink)\b", "Direct file deletion prohibited in verification routines"),
        (r"open\(.*['\"].*passwd", "Attempt to access system credential files"),
        (r"open\(.*['\"].*\.env", "Attempt to read secret environment files"),
        (r"(AWS_SECRET_ACCESS_KEY|PRIVATE_KEY|id_rsa|API_SECRET)", "Secret identifier tampering or exfiltration detected"),
        (r"requests\.(post|put|patch|delete)\b", "Direct external HTTP write/exfiltration prohibited in verification"),
        (r"urllib\.request", "Arbitrary socket or network call prohibited"),
        (r"socket\.socket\b", "Direct raw network socket forbidden in test execution"),
        (r"eval\(|exec\(", "Dynamic code evaluation (eval/exec) strictly forbidden"),
        (r"__import__\(['\"]os['\"]\)", "Obfuscated import of OS library prohibited"),
        (r"(stripe|paypal|braintree)\.(Charge|Payment|Transfer|Refund)\b", "Real payment gateway execution forbidden"),
        (r"send_payment\b|process_live_transaction\b", "Live financial transaction execution strictly prohibited"),
        (r"DROP\s+TABLE|DELETE\s+FROM\s+(users|credentials|keys)", "Destructive database operations prohibited"),
    ]

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self.workspace_root = workspace_root or ""
        self.blocked_violations: List[Dict[str, Any]] = []

    def validate_code_safety(self, code: str, context_id: str = "") -> Tuple[bool, Optional[str]]:
        """Validate safety of arbitrary code, test source, or patch."""
        for pattern, reason in self.PROHIBITED_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                violation = {
                    "context_id": context_id,
                    "pattern": pattern,
                    "reason": reason,
                    "snippet": code[:140],
                }
                self.blocked_violations.append(violation)
                return False, f"SECURITY_BLOCKED: {reason}"
        return True, None

    def validate_economic_scope(self, code: str, is_economic_policy: bool = False) -> Tuple[bool, Optional[str]]:
        """Under economic policy, ensure tests remain strictly synthetic without external API or heavy IO calls."""
        if not is_economic_policy:
            return True, None
        
        prohibited_in_economic = [
            (r"requests\.", "External HTTP requests forbidden in economic policy (must use synthetic mocks)"),
            (r"playwright|selenium|webdriver", "Heavy browser automation forbidden in economic policy"),
            (r"time\.sleep\s*\(\s*([1-9]\d*|\d+\.\d+)\s*\)", "Excessive sleep delay forbidden in economic policy"),
        ]
        for pattern, reason in prohibited_in_economic:
            if re.search(pattern, code, re.IGNORECASE):
                self.blocked_violations.append({
                    "context_id": "economic_policy_check",
                    "pattern": pattern,
                    "reason": reason,
                    "snippet": code[:140],
                })
                return False, f"ECONOMIC_POLICY_BLOCKED: {reason}"
        return True, None

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return list(self.blocked_violations)

    def clear_audit_log(self) -> None:
        self.blocked_violations.clear()
