"""
JARVIS OS — Phase 42: Memory Security Sentinel & Prompt Injection Defense
Guarantees absolute separation between passive data and executable instructions,
blocking prompt injection, fake system tags, shell exploits, and simulated approvals.
"""

from __future__ import annotations

import re
from typing import Any

from agents.experience_memory.models import ExperienceRecord


class MemorySecuritySentinel:
    """Guards memory ingestion and retrieval against prompt injection and malicious payload poisoning."""

    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
        re.compile(r"<\s*system_message\s*>", re.IGNORECASE),
        re.compile(r"\[\s*system\s*\]", re.IGNORECASE),
        re.compile(r"(fake|human)\s+approval(\s+granted)?(\s*:\s*true)?", re.IGNORECASE),
        re.compile(r"bypass\s+(security|mission_gate|sentinel)", re.IGNORECASE),
        re.compile(r"(rm\s+-rf|format\s+[a-z]:|del\s+/[fF]|Invoke-Expression|iex\b|iex\s*\(|powershell)", re.IGNORECASE),
        re.compile(r"api_key\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]", re.IGNORECASE),
        re.compile(r"fake_evidence_hash", re.IGNORECASE),
        re.compile(r"(curl|wget|fetch|Invoke-RestMethod)\s+.*(https?|ftp|tcp)", re.IGNORECASE),
        re.compile(r"exfiltrat\w*\s+(to|data|credentials|tokens|\?)", re.IGNORECASE),
        re.compile(r"(webhook\.site|attacker\.com|pastebin\.com|ngrok\.io|malicious\.org)", re.IGNORECASE),
    ]

    @classmethod
    def sanitize_data(cls, text: str) -> str:
        """Passive data sanitizer ensuring no active markup or prompt injection leaks."""
        if not text:
            return ""

        sanitized = text
        # Neutralize XML/HTML system tags
        sanitized = re.sub(r"<\s*(/?\s*(?:system|admin|eval|exec)[^>]*)>", r"[DATA_ESCAPED:\1]", sanitized, flags=re.IGNORECASE)
        # Neutralize markdown prompt injections
        for pattern in cls.INJECTION_PATTERNS:
            sanitized = pattern.sub("[POISONING_ATTEMPT_NEUTRALIZED]", sanitized)

        return sanitized

    @classmethod
    def inspect_record(cls, record: ExperienceRecord) -> tuple[bool, list[str]]:
        """
        Inspeciona todos os campos textuais de um registo de experiência.
        Retorna (is_safe, list_of_violations).
        """
        violations: list[str] = []

        fields_to_check = [
            ("outcome", record.outcome),
            ("root_cause", record.root_cause),
            ("severity", record.severity),
            ("curation_status", record.curation_status),
        ]

        for name, val in fields_to_check:
            if not isinstance(val, str):
                continue
            for pattern in cls.INJECTION_PATTERNS:
                m = pattern.search(val)
                if m:
                    violations.append(f"Security violation in '{name}': matched '{m.group(0)}' (pattern '{pattern.pattern}')")

        # Check mission_context and observation values
        def _scan_dict(d: dict[str, Any], path: str):
            for k, v in d.items():
                curr_path = f"{path}.{k}"
                if isinstance(v, str):
                    for pattern in cls.INJECTION_PATTERNS:
                        m = pattern.search(v)
                        if m:
                            violations.append(f"Security violation in '{curr_path}': matched '{m.group(0)}' (pattern '{pattern.pattern}')")
                elif isinstance(v, dict):
                    _scan_dict(v, curr_path)

        _scan_dict(record.mission_context, "mission_context")
        _scan_dict(record.observation, "observation")

        is_safe = len(violations) == 0
        return is_safe, violations
