"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Security Sentinel: Sovereign authority safeguarding against package poisoning,
remote code injection, privilege downgrades, and unauthorized economic mutations.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from agents.project_preflight.models import FilePatch, RepairPlan


class SecurityVetoError(Exception):
    """Raised when a security violation or malicious patch is detected."""
    pass


class PreflightSecuritySentinel:
    """
    Sovereign gate inspecting all repair plans and code patches before application.
    """

    SUSPICIOUS_PACKAGE_PATTERNS = [
        r"^http://", r"^https://", r"\.sh$", r"\.exe$", r"^git\+", r"malicious",
        r"backdoor", r"eval-", r"crypto-miner", r"exfiltrate",
    ]

    SUSPICIOUS_CODE_PATTERNS = [
        r"\beval\s*\(", r"\bchild_process\.exec\s*\(", r"\bexecSync\s*\(",
        r"\bcurl\s+", r"\bwget\s+", r"\brm\s+-rf\b", r"\bprocess\.exit\b",
        r"password\s*=\s*['\"]", r"secret_key\s*=\s*['\"]",
    ]

    ECONOMIC_MUTATION_PATTERNS = [
        r"\bamount\s*=", r"\bcurrency\s*=", r"\bledger\b", r"\brefund\b",
        r"\bsettle\b", r"\bfee\s*=", r"\bdiscount_rate\s*=",
    ]

    AUTH_DOWNGRADE_PATTERNS = [
        r"\bverify_token\s*=\s*False\b", r"\bauthenticated\s*=\s*True\b",
        r"\brole\s*=\s*['\"]ADMIN['\"]", r"\bdisable_auth\b",
    ]

    def inspect_repair_plan(
        self,
        repair_plan: RepairPlan,
        is_economic: bool = False,
        is_security_critical: bool = False,
    ) -> None:
        """Inspects proposed patches for security violations."""
        for patch in repair_plan.file_patches:
            self._inspect_patch_text(patch, is_economic, is_security_critical)

    def _inspect_patch_text(
        self, patch: FilePatch, is_economic: bool, is_security_critical: bool
    ) -> None:
        content = patch.patched_content

        # 1. Check for suspicious remote code execution / eval
        for pattern in self.SUSPICIOUS_CODE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                # Only raise if it was newly added in patch
                if not re.search(pattern, patch.original_content, re.IGNORECASE):
                    raise SecurityVetoError(
                        f"[Security Sentinel Veto] Padrão suspeito ou perigoso de execução detetado: {pattern}"
                    )

        # 2. Package poisoning in package.json
        if "package.json" in patch.relative_path:
            for pattern in self.SUSPICIOUS_PACKAGE_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    raise SecurityVetoError(
                        f"[Security Sentinel Veto] Tentativa de package poisoning detetada em package.json: {pattern}"
                    )

        # 3. Unauthorized Economic Mutations
        if is_economic:
            for pattern in self.ECONOMIC_MUTATION_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    if patch.original_content != patch.patched_content:
                        raise SecurityVetoError(
                            f"[Security Sentinel Veto] Mutação de lógica econômica ({pattern}) bloqueada sem aprovação humana."
                        )

        # 4. Auth Downgrades
        if is_security_critical:
            for pattern in self.AUTH_DOWNGRADE_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    raise SecurityVetoError(
                        f"[Security Sentinel Veto] Tentativa de rebaixamento de autorização/segurança detetada: {pattern}"
                    )
