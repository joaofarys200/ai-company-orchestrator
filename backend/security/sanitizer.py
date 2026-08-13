from __future__ import annotations

import re
from typing import Any


class SensitiveDataSanitizer:
    """Universal high-speed regex-based sanitizer to prevent credential leaks across all logs, telemetry, and RHO."""

    SECRET_PATTERNS = [
        # Anthropic keys (must precede general sk- pattern)
        (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}", re.IGNORECASE), "[REDACTED_ANTHROPIC_KEY]"),
        # OpenAI keys
        (re.compile(r"sk-[A-Za-z0-9_-]{20,}", re.IGNORECASE), "[REDACTED_OPENAI_KEY]"),
        # Google API keys
        (re.compile(r"AIza[0-9A-Za-z-_]{35}", re.IGNORECASE), "[REDACTED_GOOGLE_KEY]"),
        # GitHub tokens
        (re.compile(r"ghp_[A-Za-z0-9]{36}", re.IGNORECASE), "[REDACTED_GITHUB_TOKEN]"),
        # General Bearer tokens
        (re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
        # Passwords in JSON / query params
        (re.compile(r'(["\']?password["\']?\s*[:=]\s*["\']?)([^"\'\s,;]+)(["\']?)', re.IGNORECASE), r"\1[REDACTED_PASSWORD]\3"),
        # Generic API keys in key=value / json format
        (re.compile(r'(["\']?api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'\s,;]{12,})(["\']?)', re.IGNORECASE), r"\1[REDACTED_APIKEY]\3"),
        # Private Keys
        (re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    ]

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Sanitizes sensitive tokens and passwords from a string."""
        if not text or not isinstance(text, str):
            return text

        sanitized = text
        for pattern, replacement in cls.SECRET_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    @classmethod
    def sanitize_data(cls, data: Any) -> Any:
        """Recursively sanitizes dicts, lists, and primitives."""
        if isinstance(data, str):
            return cls.sanitize_text(data)
        elif isinstance(data, dict):
            return {k: cls.sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls.sanitize_data(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(cls.sanitize_data(item) for item in data)
        return data


__all__ = ["SensitiveDataSanitizer"]
