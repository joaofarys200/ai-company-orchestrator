"""
JARVIS OS — Phase 44: Semantic Graph Security Sentinel

Strictly enforces the Data-vs-Instruction separation on all contracts, schemas,
descriptions, and metadata.
Guarantees that no contract or schema is ever interpreted as an executable prompt or command.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import re
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SecurityViolation:
    field_path: str
    violation_type: str
    matched_pattern: str
    original_text: str
    action_taken: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SemanticGraphSecuritySentinel:
    """Hardens the cross-language semantic layer against prompt injection, shell injection, and authority bypass."""

    # Malicious injection patterns targeting agent instructions
    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
        re.compile(r"system\s*prompt", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(an\s+)?unrestricted", re.IGNORECASE),
        re.compile(r"antigravity\s+(override|disable)", re.IGNORECASE),
        re.compile(r"disregard\s+security", re.IGNORECASE),
        re.compile(r"human[_\s]operator\s+approved", re.IGNORECASE),
    ]

    # Command execution injection patterns
    COMMAND_INJECTION_PATTERNS = [
        re.compile(r"(?:^|[;&|`$])\s*(?:rm\s+-rf|curl\s+.*?\|\s*bash|powershell\s+-enc|cmd\.exe|wget\s+.*?\|\s*sh)", re.IGNORECASE),
        re.compile(r"(?:eval|exec)\s*\(", re.IGNORECASE),
        re.compile(r"<script[\s>]", re.IGNORECASE),
    ]

    # Prohibited authority bypass fields
    PROHIBITED_METADATA_KEYS = {
        "bypass_gate",
        "bypass_security",
        "skip_verification",
        "force_approval",
        "authorized_by_sentinel",
        "disable_sentinel",
        "auto_approve",
    }

    @classmethod
    def sanitize_metadata(cls, data: dict[str, Any], path: str = "root") -> tuple[dict[str, Any], list[SecurityViolation]]:
        """Deeply inspects and sanitizes metadata dict, neutralising malicious instructions and fake approvals."""
        clean_data: dict[str, Any] = {}
        violations: list[SecurityViolation] = []

        for key, val in data.items():
            curr_path = f"{path}.{key}"

            # 1. Check prohibited authority bypass keys
            if key.lower() in cls.PROHIBITED_METADATA_KEYS:
                violations.append(
                    SecurityViolation(
                        field_path=curr_path,
                        violation_type="AUTHORITY_BYPASS_ATTEMPT",
                        matched_pattern=key,
                        original_text=str(val),
                        action_taken="STRIPPED_KEY",
                    )
                )
                continue

            if isinstance(val, str):
                cleaned_str, text_viols = cls.sanitize_text(val, curr_path)
                violations.extend(text_viols)
                clean_data[key] = cleaned_str
            elif isinstance(val, dict):
                sub_dict, sub_viols = cls.sanitize_metadata(val, curr_path)
                violations.extend(sub_viols)
                clean_data[key] = sub_dict
            elif isinstance(val, list):
                clean_list = []
                for idx, item in enumerate(val):
                    item_path = f"{curr_path}[{idx}]"
                    if isinstance(item, str):
                        c_str, i_viols = cls.sanitize_text(item, item_path)
                        violations.extend(i_viols)
                        clean_list.append(c_str)
                    elif isinstance(item, dict):
                        s_dict, s_viols = cls.sanitize_metadata(item, item_path)
                        violations.extend(s_viols)
                        clean_list.append(s_dict)
                    else:
                        clean_list.append(item)
                clean_data[key] = clean_list
            else:
                clean_data[key] = val

        return clean_data, violations

    @classmethod
    def sanitize_text(cls, text: str, field_path: str = "text") -> tuple[str, list[SecurityViolation]]:
        """Sanitizes text fields such as schema descriptions, docstrings, or route summaries."""
        violations: list[SecurityViolation] = []
        clean = text

        # Check prompt injection
        for pat in cls.PROMPT_INJECTION_PATTERNS:
            if pat.search(clean):
                match_str = pat.search(clean).group(0) # type: ignore
                violations.append(
                    SecurityViolation(
                        field_path=field_path,
                        violation_type="PROMPT_INJECTION",
                        matched_pattern=match_str,
                        original_text=clean,
                        action_taken="NEUTRALIZED_TO_PASSIVE_DATA",
                    )
                )
                clean = pat.sub("[SANITIZED_INSTRUCTION]", clean)

        # Check command injection
        for pat in cls.COMMAND_INJECTION_PATTERNS:
            if pat.search(clean):
                match_str = pat.search(clean).group(0) # type: ignore
                violations.append(
                    SecurityViolation(
                        field_path=field_path,
                        violation_type="COMMAND_INJECTION",
                        matched_pattern=match_str,
                        original_text=clean,
                        action_taken="STRIPPED_COMMAND",
                    )
                )
                clean = pat.sub("[BLOCKED_COMMAND]", clean)

        return clean, violations
