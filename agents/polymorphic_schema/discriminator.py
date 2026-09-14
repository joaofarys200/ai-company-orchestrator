"""
JARVIS OS — Phase 47: Discriminator Resolution & Inference Engine
Resolves explicit discriminators, infers structural discriminators, and detects ambiguity.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.polymorphic_schema.models import (
    DiscriminatorDefinition,
    DiscriminatorLocation,
    DiscriminatorType,
    SchemaVariant,
    VariantStatus,
)


STANDARD_DISCRIMINATOR_FIELDS = [
    "type",
    "kind",
    "variant",
    "mode",
    "status",
    "event_type",
    "action",
    "category",
    "role",
    "schema_type",
]


class DiscriminatorEngine:
    """Discovers, validates, and infers discriminators for polymorphic unions."""

    @classmethod
    def detect_discriminator(
        cls,
        sample_payloads: List[Dict[str, Any]],
        candidate_fields: Optional[List[str]] = None,
    ) -> Optional[DiscriminatorDefinition]:
        """High-level discriminator discovery across explicit keywords and structural inference."""
        if not sample_payloads or len(sample_payloads) < 2:
            return None

        # 1. Try explicit keywords
        explicit = cls.resolve_explicit_discriminator(sample_payloads, candidate_fields)
        if explicit:
            explicit.is_explicit = True
            return explicit

        # 2. Check if we have two distinct structural clusters
        keys_list = [set(p.keys()) for p in sample_payloads if isinstance(p, dict)]
        if not keys_list:
            return None

        unique_key_sets = []
        for ks in keys_list:
            if ks not in unique_key_sets:
                unique_key_sets.append(ks)

        if len(unique_key_sets) >= 2:
            # Cluster payloads into cluster A and B
            cand_a = [p for p in sample_payloads if set(p.keys()) == unique_key_sets[0]]
            cand_b = [p for p in sample_payloads if set(p.keys()) == unique_key_sets[1]]
            disc, is_ambig = cls.infer_structural_discriminator(cand_a, cand_b)
            if disc:
                disc.is_explicit = False
                disc.type = DiscriminatorType.INFERRED_STRUCTURAL
                disc.discriminator_type = DiscriminatorType.INFERRED_STRUCTURAL
                return disc

        return None

    @classmethod
    def resolve_value_from_request(
        cls,
        field_name: str,
        body: Dict[str, Any],
        headers: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], DiscriminatorLocation]:
        """Resolves discriminator value from body, headers, or query parameters."""
        if isinstance(body, dict) and field_name in body:
            return str(body[field_name]), DiscriminatorLocation.BODY

        if headers and isinstance(headers, dict):
            # Check exact and lower-case
            for k, v in headers.items():
                if k.lower() == field_name.lower():
                    return str(v), DiscriminatorLocation.HEADER

        if query and isinstance(query, dict):
            for k, v in query.items():
                if k.lower() == field_name.lower():
                    return str(v), DiscriminatorLocation.QUERY

        return None, DiscriminatorLocation.NONE

    @classmethod
    def check_ambiguity(
        cls,
        sample_payloads: List[Dict[str, Any]],
    ) -> Tuple[bool, str]:
        """Detects whether sample payloads represent ambiguous variants that must remain UNCERTAIN."""
        if not sample_payloads or len(sample_payloads) < 2:
            return False, "Insufficient samples"

        # If an explicit discriminator exists, it's not ambiguous
        if cls.resolve_explicit_discriminator(sample_payloads) is not None:
            return False, "Explicit discriminator reliably partitions variants"

        key_sets = [set(p.keys()) for p in sample_payloads if isinstance(p, dict)]
        if not key_sets:
            return False, "No dictionary payloads"

        # Check subset relationships without explicit discriminator tag
        for i in range(len(key_sets)):
            for j in range(i + 1, len(key_sets)):
                set_a = key_sets[i]
                set_b = key_sets[j]
                if set_a != set_b and (set_a.issubset(set_b) or set_b.issubset(set_a)):
                    return True, "Ambiguidade detectada: variantes diferem apenas por campos opcionais sem discriminador explícito. Permanece UNCERTAIN (Regra 28)."

        return False, "No ambiguous subset patterns found"

    @classmethod
    def resolve_explicit_discriminator(
        cls,
        sample_payloads: List[Dict[str, Any]],
        candidate_fields: Optional[List[str]] = None,
    ) -> Optional[DiscriminatorDefinition]:
        """Scans sample payloads for explicit string or enum discriminator fields."""
        if not sample_payloads or len(sample_payloads) < 2:
            return None

        fields_to_check = candidate_fields or STANDARD_DISCRIMINATOR_FIELDS

        for candidate in fields_to_check:
            # Check if all payloads contain this field
            values_observed = []
            all_have_field = True

            for p in sample_payloads:
                if not isinstance(p, dict) or candidate not in p:
                    all_have_field = False
                    break
                val = p[candidate]
                if not isinstance(val, (str, int, bool)):
                    all_have_field = False
                    break
                values_observed.append(str(val))

            if not all_have_field:
                continue

            unique_values = sorted(list(set(values_observed)))
            # A valid discriminator MUST have at least 2 distinct values across samples
            if len(unique_values) >= 2:
                # Build value-to-variant mapping
                mapping = {v: f"var_{candidate}_{v.lower().replace('.', '_').replace('-', '_')}" for v in unique_values}
                return DiscriminatorDefinition(
                    field=candidate,
                    location=DiscriminatorLocation.BODY,
                    discriminator_type=DiscriminatorType.STRING_ENUM,
                    observed_values=unique_values,
                    mapping=mapping,
                    confidence=1.0,
                    is_inferred=False,
                )

        return None

    @classmethod
    def infer_structural_discriminator(
        cls,
        variant_a_samples: List[Dict[str, Any]],
        variant_b_samples: List[Dict[str, Any]],
    ) -> Tuple[Optional[DiscriminatorDefinition], bool]:
        """Infers a structural discriminator (e.g. FIELD_PRESENCE) between two clusters.
        
        Returns:
            (DiscriminatorDefinition, is_ambiguous)
        """
        if not variant_a_samples or not variant_b_samples:
            return None, True

        # Extract all keys present in A and B
        keys_a = set()
        for p in variant_a_samples:
            if isinstance(p, dict):
                keys_a.update(p.keys())

        keys_b = set()
        for p in variant_b_samples:
            if isinstance(p, dict):
                keys_b.update(p.keys())

        # Check for exclusive presence
        exclusive_to_a = keys_a - keys_b
        exclusive_to_b = keys_b - keys_a

        # If either exclusive set is empty, one shape is a subset of the other.
        # Without an explicit discriminator, this cannot be distinguished from optional fields => AMBIGUOUS (Regra 28)
        if not exclusive_to_a or not exclusive_to_b:
            return None, True

        # Prefer field with 100% presence in one cluster and 0% in the other
        for cand in sorted(exclusive_to_b):
            present_in_b = all(isinstance(p, dict) and cand in p for p in variant_b_samples)
            absent_in_a = all(isinstance(p, dict) and cand not in p for p in variant_a_samples)
            if present_in_b and absent_in_a:
                return (
                    DiscriminatorDefinition(
                        field=cand,
                        location=DiscriminatorLocation.BODY,
                        discriminator_type=DiscriminatorType.FIELD_PRESENCE,
                        observed_values=[f"has_{cand}", f"no_{cand}"],
                        mapping={
                            f"has_{cand}": "variant_b",
                            f"no_{cand}": "variant_a",
                        },
                        confidence=0.80,
                        is_inferred=True,
                    ),
                    False,
                )

        for cand in sorted(exclusive_to_a):
            present_in_a = all(isinstance(p, dict) and cand in p for p in variant_a_samples)
            absent_in_b = all(isinstance(p, dict) and cand not in p for p in variant_b_samples)
            if present_in_a and absent_in_b:
                return (
                    DiscriminatorDefinition(
                        field=cand,
                        location=DiscriminatorLocation.BODY,
                        discriminator_type=DiscriminatorType.FIELD_PRESENCE,
                        observed_values=[f"has_{cand}", f"no_{cand}"],
                        mapping={
                            f"has_{cand}": "variant_a",
                            f"no_{cand}": "variant_b",
                        },
                        confidence=0.80,
                        is_inferred=True,
                    ),
                    False,
                )

        # Subset with partial presence (e.g. Variant A: {name, email}, Variant B: {name, email, permissions?})
        # If permissions is optional in B, we cannot reliably discriminate without explicit tag => AMBIGUOUS
        return None, True

    @classmethod
    def validate_discriminator_coverage(
        cls,
        discriminator: DiscriminatorDefinition,
        variants: List[SchemaVariant],
    ) -> Tuple[bool, List[str]]:
        """Validates that each variant maps to a distinct discriminator value."""
        errors: List[str] = []
        if not discriminator.field:
            return False, ["Discriminator field is empty"]

        mapped_variants = set(discriminator.mapping.values())
        actual_variants = {v.variant_id for v in variants}

        missing = actual_variants - mapped_variants
        if missing:
            errors.append(f"Variants without discriminator mapping: {sorted(missing)}")

        # Check for collision in values
        values_seen = set()
        for val in discriminator.observed_values:
            if val in values_seen:
                errors.append(f"Duplicate discriminator value detected: '{val}'")
            values_seen.add(val)

        return len(errors) == 0, errors
