from __future__ import annotations

import re
from typing import Any


class SensitiveDataSanitizer:
    """Universal high-speed multi-layer sanitizer to prevent credential and secret leaks across logs, telemetry, SQLite, and RHO."""

    SECRET_PATTERNS = [
        # Private Keys
        (re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
        
        # Anthropic keys (must precede general sk- pattern)
        (re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}", re.IGNORECASE), "[REDACTED_ANTHROPIC_KEY]"),
        
        # OpenAI keys (project and standard)
        (re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}", re.IGNORECASE), "[REDACTED_OPENAI_KEY]"),
        
        # Google API keys
        (re.compile(r"AIza[0-9A-Za-z-_]{30,}", re.IGNORECASE), "[REDACTED_GOOGLE_KEY]"),
        
        # GitHub Fine-Grained Personal Access Tokens
        (re.compile(r"github_pat_[A-Za-z0-9_]{20,}", re.IGNORECASE), "[REDACTED_GITHUB_PAT]"),
        
        # GitHub Classic Personal Access Tokens (variable length >= 16)
        (re.compile(r"gh[pousr]_[A-Za-z0-9_]{16,}", re.IGNORECASE), "[REDACTED_GITHUB_TOKEN]"),
        
        # JWT Tokens
        (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}", re.IGNORECASE), "[REDACTED_JWT_TOKEN]"),
        
        # Bearer tokens in headers or strings
        (re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
        
        # Authorization Headers
        (re.compile(r"(Authorization\s*:\s*(?:Basic|Bearer|Token)\s+)[^\r\n]+", re.IGNORECASE), r"\1[REDACTED_AUTH_HEADER]"),
        
        # Passwords in JSON, key-value, query params
        (re.compile(r'(["\']?(?:password|passwd|pwd|secret_key|api_secret|client_secret)["\']?\s*[:=]\s*["\']?)([^"\'\s,;]+)(["\']?)', re.IGNORECASE), r"\1[REDACTED_PASSWORD]\3"),
        
        # Generic API keys in key=value / json format
        (re.compile(r'(["\']?(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret)["\']?\s*[:=]\s*["\']?)([^"\'\s,;&]{10,})(["\']?)', re.IGNORECASE), r"\1[REDACTED_APIKEY]\3"),
        
        # .env secret assignments
        (re.compile(r"((?:OPENAI_API_KEY|ANTHROPIC_API_KEY|GEMINI_API_KEY|STRIPE_SECRET_KEY|GITHUB_TOKEN|SECRET_KEY|DATABASE_URL)\s*=\s*['\"]?)([^'\"\r\n\s]{8,})(['\"]?)", re.IGNORECASE), r"\1[REDACTED_ENV_SECRET]\3"),
    ]

    SENSITIVE_KEY_NAMES = {
        "password",
        "passwd",
        "pwd",
        "secret",
        "secret_key",
        "api_key",
        "apikey",
        "access_token",
        "auth_token",
        "client_secret",
        "token",
        "authorization",
        "private_key",
    }

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Sanitizes sensitive tokens, passwords, and secrets from a string."""
        if not text or not isinstance(text, str):
            return text

        sanitized = text
        for pattern, replacement in cls.SECRET_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    @classmethod
    def sanitize_data(cls, data: Any) -> Any:
        """Recursively sanitizes dicts, lists, exceptions, and primitives."""
        if isinstance(data, str):
            return cls.sanitize_text(data)
        elif isinstance(data, dict):
            sanitized_dict = {}
            for k, v in data.items():
                if isinstance(v, str):
                    val = cls.sanitize_text(v)
                    if val != v:
                        sanitized_dict[k] = val
                    elif isinstance(k, str) and k.lower() in cls.SENSITIVE_KEY_NAMES:
                        sanitized_dict[k] = "[REDACTED_SENSITIVE_VALUE]"
                    else:
                        sanitized_dict[k] = val
                elif isinstance(k, str) and k.lower() in cls.SENSITIVE_KEY_NAMES:
                    sanitized_dict[k] = "[REDACTED_SENSITIVE_VALUE]"
                else:
                    sanitized_dict[k] = cls.sanitize_data(v)
            return sanitized_dict
        elif isinstance(data, list):
            return [cls.sanitize_data(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(cls.sanitize_data(item) for item in data)
        elif isinstance(data, set):
            return {cls.sanitize_data(item) for item in data}
        elif isinstance(data, Exception):
            return cls.sanitize_text(str(data))
        return data


__all__ = ["SensitiveDataSanitizer"]
