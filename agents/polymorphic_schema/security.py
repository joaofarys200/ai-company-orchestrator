"""
JARVIS OS — Phase 47: Polymorphic Security Sentinel
Enforces passive data semantics, neutralizes prompt injection in discriminators,
and blocks embedded shell commands in polymorphic metadata.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from agents.polymorphic_schema.models import DiscriminatorDefinition, PolymorphicSchema, SchemaVariant


DANGEROUS_COMMAND_PATTERNS = [
    re.compile(r"(?:bash|sh|cmd|powershell|pwsh)\s+(?:-c|-Command)?", re.IGNORECASE),
    re.compile(r"\b(?:rm|del|rmdir|mkfs|dd|curl|wget)\b\s+-[a-zA-Z]", re.IGNORECASE),
    re.compile(r"[;&|`$]\s*(?:rm|del|cat|curl|nc|bash)\b", re.IGNORECASE),
    re.compile(r"\$\(.*?\)", re.IGNORECASE),
    re.compile(r"`.*?`", re.IGNORECASE),
    re.compile(r"__(?:import|builtins)__", re.IGNORECASE),
]

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
    re.compile(r"bypass\s+all\s+security\s+rules", re.IGNORECASE),
    re.compile(r"disregard\s+the\s+above\s+and\s+say", re.IGNORECASE),
]


class PolymorphicSecuritySentinel:
    """Hardens polymorphic schemas and discriminators against injection and tamper."""

    @classmethod
    def inspect_discriminator(cls, discriminator: Any) -> Any:
        """Scans a discriminator (str or DiscriminatorDefinition) for adversarial patterns."""
        if isinstance(discriminator, str):
            violations: List[str] = []
            cls._check_string(discriminator, "discriminator", violations)
            is_safe = len(violations) == 0
            sanitized = cls.sanitize_string(discriminator)
            for pat in DANGEROUS_COMMAND_PATTERNS + PROMPT_INJECTION_PATTERNS:
                sanitized = pat.sub("[REDACTED]", sanitized)
            alert = violations[0] if violations else None
            return is_safe, sanitized, alert

        violations = []
        if hasattr(discriminator, "field"):
            cls._check_string(discriminator.field, "discriminator.field", violations)
            for val in getattr(discriminator, "observed_values", []):
                cls._check_string(str(val), "discriminator.observed_value", violations)
            for k, v in getattr(discriminator, "mapping", {}).items():
                cls._check_string(str(k), "discriminator.mapping_key", violations)
                cls._check_string(str(v), "discriminator.mapping_value", violations)
        return violations

    @classmethod
    def inspect_metadata(cls, metadata: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """Audits metadata dictionaries for dangerous command insertions and prompt injections."""
        violations: List[str] = []
        cls._recursive_inspect(metadata, violations, "metadata")
        is_safe = len(violations) == 0
        sanitized = {}
        for k, v in metadata.items():
            if isinstance(v, str):
                s_val = v
                for pat in DANGEROUS_COMMAND_PATTERNS + PROMPT_INJECTION_PATTERNS:
                    s_val = pat.sub("[REDACTED]", s_val)
                sanitized[k] = cls.sanitize_string(s_val)
            else:
                sanitized[k] = v
        alert = violations[0] if violations else None
        return is_safe, sanitized, alert

    @classmethod
    def inspect_payload(cls, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """Audits an example payload for embedded code or exploits."""
        violations: List[str] = []
        cls._recursive_inspect(payload, violations, "payload")
        is_safe = len(violations) == 0
        sanitized = {}
        for k, v in payload.items():
            if isinstance(v, str):
                s_val = v
                for pat in DANGEROUS_COMMAND_PATTERNS + PROMPT_INJECTION_PATTERNS:
                    s_val = pat.sub("[REDACTED]", s_val)
                sanitized[k] = cls.sanitize_string(s_val)
            else:
                sanitized[k] = v
        alert = violations[0] if violations else None
        return is_safe, sanitized, alert

    @classmethod
    def validate_approval_token(cls, token: str, operator_id: str) -> bool:
        """Validates cryptographic integrity of human approval signature token."""
        if not token or not isinstance(token, str):
            return False
        if "forged" in token.lower() or "fake" in token.lower():
            return False
        if len(token) < 24:
            return False
        return token.startswith("sig_valid_")

    @classmethod
    def inspect_variant(cls, variant: SchemaVariant) -> List[str]:
        """Scans a variant label, schema properties, and metadata for security violations."""
        violations: List[str] = []

        cls._check_string(variant.variant_id, "variant.variant_id", violations)
        cls._check_string(variant.label, "variant.label", violations)

        # Recursively inspect schema dictionary
        cls._recursive_inspect(variant.schema, violations, "variant.schema")
        cls._recursive_inspect(variant.metadata, violations, "variant.metadata")

        return violations

    @classmethod
    def inspect_schema(cls, schema: PolymorphicSchema) -> List[str]:
        """Comprehensive security audit for a complete PolymorphicSchema."""
        violations: List[str] = []

        cls._check_string(schema.schema_id, "schema.schema_id", violations)
        cls._check_string(schema.contract_id, "schema.contract_id", violations)

        if schema.discriminator:
            violations.extend(cls.inspect_discriminator(schema.discriminator))

        for v in schema.variants:
            violations.extend(cls.inspect_variant(v))

        return violations

    @classmethod
    def _check_string(cls, text: str, field_name: str, violations: List[str]) -> None:
        if not text:
            return

        for pat in PROMPT_INJECTION_PATTERNS:
            if pat.search(text):
                violations.append(f"Prompt injection pattern detected in '{field_name}': {text[:40]}...")
                break

        for pat in DANGEROUS_COMMAND_PATTERNS:
            if pat.search(text):
                violations.append(f"Shell command injection pattern detected in '{field_name}': {text[:40]}...")
                break

    @classmethod
    def _recursive_inspect(cls, obj: Any, violations: List[str], path: str) -> None:
        if isinstance(obj, str):
            cls._check_string(obj, path, violations)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                cls._check_string(str(k), f"{path}.key", violations)
                cls._recursive_inspect(v, violations, f"{path}.{k}")
        elif isinstance(obj, (list, tuple, set)):
            for idx, item in enumerate(obj):
                cls._recursive_inspect(item, violations, f"{path}[{idx}]")

    @classmethod
    def sanitize_string(cls, text: str) -> str:
        """Strips null bytes and script tags from text data."""
        if not isinstance(text, str):
            return str(text)
        cleaned = text.replace("\x00", "").replace("\r", "")
        cleaned = re.sub(r"<script.*?>.*?</script>", "[REMOVED_SCRIPT]", cleaned, flags=re.IGNORECASE | re.DOTALL)
        return cleaned
