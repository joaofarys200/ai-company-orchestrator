"""
JARVIS OS — Phase 45: Runtime Discovery Security & Redaction Engine
Enforces strict redaction of sensitive credentials and neutralizes prompt/command injections
in observed runtime network traffic.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple


class RuntimeDiscoverySecurity:
    """Provides deep payload and header redaction and passive data sanitization."""

    # Headers containing credentials or tokens that must never be recorded
    SENSITIVE_HEADER_NAMES: set[str] = {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "apikey",
        "proxy-authorization",
        "x-auth-token",
        "x-csrf-token",
        "x-xsrf-token",
    }

    # Field names in payloads containing sensitive data
    SENSITIVE_FIELD_NAMES: set[str] = {
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "private_key",
        "api_key",
        "apikey",
        "credit_card",
        "card_number",
        "cvv",
        "ssn",
        "bearer",
    }

    # Prompt injection patterns targeting LLMs/agents
    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
        re.compile(r"system\s*prompt", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(an\s+)?unrestricted", re.IGNORECASE),
        re.compile(r"antigravity\s+(override|disable)", re.IGNORECASE),
        re.compile(r"disregard\s+security", re.IGNORECASE),
        re.compile(r"human[_\s]operator\s+approved", re.IGNORECASE),
    ]

    # Command execution patterns
    COMMAND_INJECTION_PATTERNS = [
        re.compile(r"(?:^|[;&|`$])\s*(?:rm\s+-rf|curl\s+.*?\|\s*bash|powershell\s+-enc|cmd\.exe|wget\s+.*?\|\s*sh)", re.IGNORECASE),
        re.compile(r"(?:eval|exec)\s*\(", re.IGNORECASE),
        re.compile(r"<script[\s>]", re.IGNORECASE),
    ]

    PROHIBITED_AUTHORITY_KEYS: set[str] = {
        "bypass_gate",
        "bypass_security",
        "skip_verification",
        "force_approval",
        "authorized_by_sentinel",
        "disable_sentinel",
        "auto_approve",
    }

    @classmethod
    def redact_headers(cls, headers: dict[str, str]) -> tuple[dict[str, str], int]:
        """Redacts sensitive HTTP headers like Authorization, Cookie, and API keys."""
        redacted_count = 0
        clean: dict[str, str] = {}
        for k, v in headers.items():
            k_lower = k.lower().strip()
            if k_lower in cls.SENSITIVE_HEADER_NAMES:
                clean[k] = "[REDACTED_CREDENTIAL]"
                redacted_count += 1
            else:
                # Also check if value looks like a Bearer token or JWT
                if re.match(r"^Bearer\s+[A-Za-z0-9\-_.]+", str(v), re.IGNORECASE):
                    clean[k] = "Bearer [REDACTED_TOKEN]"
                    redacted_count += 1
                else:
                    clean[k] = str(v)
        return clean, redacted_count

    @classmethod
    def redact_payload(cls, data: Any, path: str = "root") -> tuple[Any, int, list[str]]:
        """Deeply sanitizes payload data, redacting sensitive field values and stripping injections."""
        redacted_count = 0
        security_alerts: list[str] = []

        if isinstance(data, dict):
            clean_dict: dict[str, Any] = {}
            for k, v in data.items():
                curr_path = f"{path}.{k}"
                k_lower = str(k).lower().strip()

                # Check prohibited authority keys
                if k_lower in cls.PROHIBITED_AUTHORITY_KEYS:
                    security_alerts.append(f"Authority bypass attempt stripped at '{curr_path}'")
                    continue

                if k_lower in cls.SENSITIVE_FIELD_NAMES:
                    clean_dict[k] = "[REDACTED_CREDENTIAL]"
                    redacted_count += 1
                else:
                    sub_val, sub_cnt, sub_alerts = cls.redact_payload(v, curr_path)
                    redacted_count += sub_cnt
                    security_alerts.extend(sub_alerts)
                    clean_dict[k] = sub_val
            return clean_dict, redacted_count, security_alerts

        elif isinstance(data, list):
            clean_list: list[Any] = []
            for idx, item in enumerate(data):
                curr_path = f"{path}[{idx}]"
                sub_val, sub_cnt, sub_alerts = cls.redact_payload(item, curr_path)
                redacted_count += sub_cnt
                security_alerts.extend(sub_alerts)
                clean_list.append(sub_val)
            return clean_list, redacted_count, security_alerts

        elif isinstance(data, str):
            clean_str = data

            # Check prompt injections
            for pat in cls.PROMPT_INJECTION_PATTERNS:
                if pat.search(clean_str):
                    security_alerts.append(f"Prompt injection neutralized at '{path}'")
                    clean_str = pat.sub("[SANITIZED_INSTRUCTION]", clean_str)

            # Check command injections
            for pat in cls.COMMAND_INJECTION_PATTERNS:
                if pat.search(clean_str):
                    security_alerts.append(f"Command injection stripped at '{path}'")
                    clean_str = pat.sub("[BLOCKED_COMMAND]", clean_str)

            return clean_str, redacted_count, security_alerts

        return data, redacted_count, security_alerts

    @classmethod
    def sanitize_headers(cls, headers: dict[str, str]) -> dict[str, str]:
        """Convenience method returning sanitized headers dictionary."""
        clean, _ = cls.redact_headers(headers)
        return clean

    @classmethod
    def sanitize_payload(cls, payload: Any) -> Any:
        """Convenience method returning sanitized payload without counts/alerts."""
        clean, _, _ = cls.redact_payload(payload)
        return clean

    @classmethod
    def inspect_for_injection(cls, text: str) -> tuple[bool, str]:
        """Inspects arbitrary text or metadata for prompt/command injection patterns."""
        if not isinstance(text, str):
            return True, ""

        for pat in cls.PROMPT_INJECTION_PATTERNS:
            if pat.search(text):
                return False, f"SUSPICIOUS_PATTERN_DETECTED: Prompt injection pattern matched ({pat.pattern})"

        for pat in cls.COMMAND_INJECTION_PATTERNS:
            if pat.search(text):
                return False, f"SUSPICIOUS_PATTERN_DETECTED: Command injection pattern matched ({pat.pattern})"

        # Check suspicious authority claims
        text_lower = text.lower()
        if "approval_confirmed" in text_lower or "system_override" in text_lower or "root admin" in text_lower:
            return False, "SUSPICIOUS_PATTERN_DETECTED: Fake authority / system override claim detected"

        return True, ""

    @classmethod
    def neutralize_data(cls, text: str) -> str:
        """Sanitizes text by stripping prompt/command injections while keeping it inert data."""
        clean, _, _ = cls.redact_payload(text)
        return str(clean)

