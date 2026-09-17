"""
JARVIS OS — Phase 54: Repair Security Sentinel
Enforces sovereign security oversight, preventing patch poisoning, dependency poisoning, and unauthorized mutations.
"""

from __future__ import annotations

import re
from typing import List

from agents.project_preflight.security import SecurityVetoError
from agents.verified_repair.models import FilePatchDiff, RepairCandidate


class RepairSecuritySentinel:
    """
    Sovereign security watchdog for verified repair synthesis.
    Vetoes any repair that introduces remote code execution, package poisoning, auth downgrade, or economic mutation.
    """

    SUSPICIOUS_PATTERNS = [
        r"\beval\s*\(",
        r"\bFunction\s*\(",
        r"\bchild_process\b",
        r"\bexec\s*\(",
        r"https?://[^\s'\"]+\.(sh|exe|bat|ps1)",
        r"\bcurl\s+-s",
        r"\bwget\s+",
        r"powershell\s+-enc",
    ]

    PACKAGE_POISON_PATTERNS = [
        r"https?://",
        r"git\+https?://",
        r"file://",
        r"\b(evil|pwned|malicious|exfiltrate)\b",
    ]

    ECONOMIC_PATTERNS = [
        r"\bamount\s*=",
        r"\bprice\s*=",
        r"\bfee\s*=",
        r"\bcurrency\b",
        r"\bledger\b",
        r"\brefund\b",
        r"\bidempotency\b",
    ]

    AUTH_PATTERNS = [
        r"\bverify_token\s*=",
        r"\bcheck_auth\b",
        r"\bis_admin\s*=",
        r"\bpermissions\s*=",
        r"\bjwt\.decode\(.*verify=False",
    ]

    def inspect_candidate(
        self,
        candidate: RepairCandidate,
        is_economic: bool = False,
        is_security_critical: bool = False,
    ) -> None:
        """Inspects all patches in a candidate for malicious or unauthorized patterns."""
        for patch in candidate.patches:
            self._inspect_patch(patch, is_economic, is_security_critical)

    def _inspect_patch(
        self,
        patch: FilePatchDiff,
        is_economic: bool,
        is_security_critical: bool,
    ) -> None:
        content = patch.patched_content

        # 1. Suspicious Remote Execution Patterns
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                if not re.search(pattern, patch.original_content, re.IGNORECASE):
                    raise SecurityVetoError(
                        f"[Security Sentinel Veto] Padrão de código perigoso ou execução remota detetado: {pattern}"
                    )

        # 2. Package Poisoning in package.json
        if "package.json" in patch.relative_path:
            for pattern in self.PACKAGE_POISON_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    raise SecurityVetoError(
                        f"[Security Sentinel Veto] Tentativa de package poisoning detetada em package.json: {pattern}"
                    )

        # 3. Economic Logic Protection
        if is_economic:
            for pattern in self.ECONOMIC_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    if patch.original_content != patch.patched_content:
                        raise SecurityVetoError(
                            f"[Security Sentinel Veto] Mutação de lógica económica ({pattern}) bloqueada sem aprovação humana."
                        )

        # 4. Auth Downgrade Protection
        if is_security_critical:
            for pattern in self.AUTH_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    if patch.original_content != patch.patched_content:
                        raise SecurityVetoError(
                            f"[Security Sentinel Veto] Rebaixamento de autorização/segurança ({pattern}) bloqueado sem aprovação humana."
                        )
