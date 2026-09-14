"""
JARVIS OS — Phase 49: Contract Normalizer
Normalizes disparate type systems (OpenAPI, JSONSchema, TypeScript, Python) into language-agnostic canonical models.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from agents.build_contract_extraction.models import (
    ContractEndpoint,
    ContractField,
    ContractType,
    TypeKind,
)


class ContractNormalizer:
    """
    Normalizes schema definitions into canonical representations.
    Provides deterministic structural hashing to detect semantic equivalence across languages.
    """

    SCALAR_MAPPINGS = {
        # String types
        "string": "string",
        "str": "string",
        "text": "string",
        "uuid": "string",
        "date": "string",
        "date-time": "string",
        # Numeric types
        "integer": "integer",
        "int": "integer",
        "int32": "integer",
        "int64": "integer",
        "number": "number",
        "float": "number",
        "double": "number",
        # Boolean types
        "boolean": "boolean",
        "bool": "boolean",
        # Any / null
        "any": "any",
        "null": "null",
        "none": "null",
    }

    @classmethod
    def normalize_type_name(cls, raw_type: str) -> str:
        """Normalizes a raw language type string to canonical type name."""
        cleaned = raw_type.strip().lower()
        return cls.SCALAR_MAPPINGS.get(cleaned, raw_type)

    @classmethod
    def compute_structural_hash(cls, contract_type: ContractType) -> str:
        """Computes a deterministic SHA-256 hash of a type's structural signature."""
        prop_reprs = []
        for prop_name, field_def in sorted(contract_type.properties.items()):
            canonical_type = cls.normalize_type_name(field_def.field_type)
            req_str = "req" if field_def.required else "opt"
            null_str = "null" if field_def.nullable else "notnull"
            prop_reprs.append(f"{prop_name}:{canonical_type}:{req_str}:{null_str}")

        variant_reprs = []
        for v in sorted(contract_type.variants, key=lambda x: x.variant_id):
            variant_reprs.append(f"{v.variant_id}:{v.discriminator_value}")

        enum_reprs = [str(x) for x in sorted(contract_type.enum_values, key=lambda x: str(x))]

        struct_str = (
            f"name={contract_type.name}|kind={contract_type.kind.value}|"
            f"props=[{','.join(prop_reprs)}]|variants=[{','.join(variant_reprs)}]|"
            f"enums=[{','.join(enum_reprs)}]"
        )
        return hashlib.sha256(struct_str.encode("utf-8")).hexdigest()

    @classmethod
    def are_structurally_equivalent(cls, type_a: ContractType, type_b: ContractType) -> bool:
        """Determines whether two contract types from different languages share identical schema structures."""
        return cls.compute_structural_hash(type_a) == cls.compute_structural_hash(type_b)
