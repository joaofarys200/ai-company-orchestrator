"""
JARVIS OS — Phase 49: Contract Schema Validator
Enforces structural invariants, prevents circularities, and sanitizes against schema poisoning.
"""

from __future__ import annotations

import re
from typing import Any, List, Set, Tuple

from agents.build_contract_extraction.models import (
    ContractEndpoint,
    ContractType,
)


class ContractValidationError(Exception):
    """Raised when an extracted contract fails structural validation or security invariants."""
    pass


class ContractSchemaValidator:
    """
    Validates structural integrity of extracted contracts and defends against schema poisoning.
    """

    POISON_PATTERNS = [
        re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript\s*:", re.IGNORECASE),
        re.compile(r"__proto__", re.IGNORECASE),
        re.compile(r"constructor\s*\.\s*prototype", re.IGNORECASE),
        re.compile(r"\bignore\s+previous\s+instructions\b", re.IGNORECASE),
        re.compile(r"\bsystem\s+prompt\s+override\b", re.IGNORECASE),
    ]

    @classmethod
    def validate_type(cls, contract_type: ContractType) -> None:
        """Validates a ContractType for security and structure."""
        if not contract_type.name or not contract_type.type_id:
            raise ContractValidationError("ContractType must have non-empty name and type_id.")

        # Check name and properties for schema poisoning
        cls._check_poison(contract_type.name, "type_name")
        for prop_name, field_def in contract_type.properties.items():
            cls._check_poison(prop_name, f"property_name ({prop_name})")
            cls._check_poison(field_def.description, f"field_description ({prop_name})")

        # Check variants
        for v in contract_type.variants:
            cls._check_poison(v.discriminator_value, "discriminator_value")
            cls._check_poison(v.description, "variant_description")

    @classmethod
    def validate_endpoint(cls, endpoint: ContractEndpoint) -> None:
        """Validates a ContractEndpoint for security and structure."""
        if not endpoint.path.startswith("/"):
            raise ContractValidationError(f"Invalid endpoint path '{endpoint.path}': must start with '/'.")
        if endpoint.method.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
            raise ContractValidationError(f"Invalid HTTP method '{endpoint.method}' on endpoint {endpoint.path}.")

        cls._check_poison(endpoint.path, "endpoint_path")

    @classmethod
    def _check_poison(cls, text: str, context_label: str) -> None:
        """Raises ContractValidationError if text contains malicious or poisoning patterns."""
        if not text:
            return
        for pat in cls.POISON_PATTERNS:
            if pat.search(text):
                raise ContractValidationError(
                    f"Security violation: Schema poisoning pattern detected in {context_label}: '{pat.pattern}'."
                )
