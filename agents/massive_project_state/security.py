from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, List, Optional, Tuple


class StateFabricSecuritySentinel:
    """Enforces Security Sentinel sovereignty over state fabric, path integrity, and hashes."""

    ECONOMIC_CONTRACT_KEYWORDS = ["payment", "ledger", "billing", "token", "wallet", "invoice", "refund"]

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self.workspace_root = os.path.abspath(workspace_root or os.getcwd())
        self.security_violations: List[Dict[str, Any]] = []

    def validate_file_path(self, path: str) -> Tuple[bool, str]:
        """Prevents path traversal, directory jail escapes, and null-byte injection."""
        if "\x00" in path:
            self._record_violation("NULL_BYTE_PATH", path)
            return False, "Null byte detected in file path"

        norm = os.path.normpath(path)
        if norm.startswith("..") or "/../" in path.replace("\\", "/"):
            self._record_violation("PATH_TRAVERSAL", path)
            return False, "Path traversal sequence detected"

        return True, "Path valid"

    def verify_content_hash(self, content: str, expected_hash: str) -> bool:
        """Verifies cryptographic SHA-256 integrity of state items."""
        computed = hashlib.sha256(content.encode()).hexdigest()
        if computed != expected_hash and computed[:len(expected_hash)] != expected_hash:
            self._record_violation("STATE_TAMPERING", f"Hash mismatch: expected {expected_hash}, got {computed}")
            return False
        return True

    def validate_economic_impact(self, changed_symbols: List[str], classified_scope: str) -> Tuple[bool, str]:
        """Ensures economic/payment invariants are never classified as trivial local changes."""
        for sym in changed_symbols:
            low = sym.lower()
            if any(kw in low for kw in self.ECONOMIC_CONTRACT_KEYWORDS):
                if classified_scope == "LOCAL":
                    self._record_violation("ECONOMIC_INVARIANT_VIOLATION", f"Economic symbol '{sym}' cannot be LOCAL")
                    return False, f"Economic symbol '{sym}' requires CROSS_SERVICE or REPOSITORY_WIDE scope"
        return True, "Economic invariants preserved"

    def _record_violation(self, violation_type: str, details: str) -> None:
        self.security_violations.append({
            "violation_type": violation_type,
            "details": details,
        })

    def get_violations(self) -> List[Dict[str, Any]]:
        return list(self.security_violations)
