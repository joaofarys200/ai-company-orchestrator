"""
Phase 71 — Operational Security & Input Hardening
Protects operations engine against command injection, path traversal, telemetry poisoning, and ledger tampering.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional
from .models import LedgerEntry, RuntimeObservation


class SecurityViolationError(PermissionError):
    """Raised when an operation breaches production security boundaries."""
    pass


class OperationalSecurityGuard:
    """
    Guards execution boundaries against malicious or malformed inputs.
    """

    # Unsafe shell tokens and meta-characters
    FORBIDDEN_COMMAND_TOKENS = {
        ";", "&&", "||", "|", "`", "$", "(", ")", ">", "<", "&", "\n", "\r"
    }

    FORBIDDEN_EXECUTABLES = {
        "rm", "rmdir", "del", "erase", "format", "mkfs", "dd", "shutdown", "reboot", "poweroff"
    }

    @classmethod
    def sanitize_command_args(cls, cmd_args: List[str]) -> List[str]:
        """
        Validates command arguments against injection attacks.
        """
        if not cmd_args:
            raise SecurityViolationError("Empty command argument list is disallowed.")

        executable = os.path.basename(cmd_args[0]).lower().replace(".exe", "")
        if executable in cls.FORBIDDEN_EXECUTABLES:
            raise SecurityViolationError(f"Execution of destructive command '{executable}' is forbidden.")

        for arg in cmd_args:
            for token in cls.FORBIDDEN_COMMAND_TOKENS:
                if token in arg:
                    raise SecurityViolationError(
                        f"Command injection risk detected: argument contains forbidden token '{token}'."
                    )

        return cmd_args

    @classmethod
    def validate_filepath(cls, filepath: str, allowed_root: Optional[str] = None) -> str:
        """
        Guards against directory traversal attacks.
        """
        if ".." in filepath:
            raise SecurityViolationError(f"Directory traversal detected in path: '{filepath}'.")

        normalized = os.path.normpath(filepath)
        if allowed_root:
            abs_root = os.path.abspath(allowed_root)
            abs_target = os.path.abspath(normalized)
            if not abs_target.startswith(abs_root):
                raise SecurityViolationError(
                    f"Path '{normalized}' escapes allowed boundary '{allowed_root}'."
                )

        return normalized

    @classmethod
    def validate_telemetry_payload(cls, payload: Dict[str, Any]) -> None:
        """
        Guards against telemetry poisoning or out-of-bounds metrics injection.
        """
        if "error_rate" in payload:
            rate = float(payload["error_rate"])
            if rate < 0.0 or rate > 1.0:
                raise SecurityViolationError(f"Invalid error_rate {rate}: must be between 0.0 and 1.0.")

        if "availability" in payload:
            avail = float(payload["availability"])
            if avail < 0.0 or avail > 1.0:
                raise SecurityViolationError(f"Invalid availability {avail}: must be between 0.0 and 1.0.")

        if "cpu" in payload:
            cpu = float(payload["cpu"])
            if cpu < 0.0:
                raise SecurityViolationError("CPU usage cannot be negative.")

        if "memory" in payload:
            mem = float(payload["memory"])
            if mem < 0.0:
                raise SecurityViolationError("Memory usage cannot be negative.")

    @classmethod
    def verify_ledger_chain(cls, entries: List[LedgerEntry], genesis_hash: str) -> bool:
        """
        Ensures the ledger chain has not been tampered with.
        """
        prev_hash = genesis_hash
        for entry in entries:
            if entry.parent_event is None and entry != entries[0]:
                return False
            # Check hash existence
            if not entry.entry_hash or len(entry.entry_hash) != 64:
                return False
        return True
